import Foundation

enum NexusAPIError: LocalizedError {
    case badURL
    case http(Int)
    case empty
    case decoding(Error)

    var errorDescription: String? {
        switch self {
        case .badURL: return "URL de API inválida"
        case .http(let code): return "API HTTP \(code)"
        case .empty: return "Respuesta vacía"
        case .decoding(let err): return "JSON: \(Self.describeDecodingError(err))"
        }
    }

    private static func describeDecodingError(_ error: Error) -> String {
        guard let error = error as? DecodingError else {
            return error.localizedDescription
        }
        switch error {
        case .keyNotFound(let key, let context):
            return "falta «\(key.stringValue)» en \(path(context.codingPath))"
        case .typeMismatch(let type, let context):
            return "tipo \(type) inválido en \(path(context.codingPath))"
        case .valueNotFound(let type, let context):
            return "valor \(type) ausente en \(path(context.codingPath))"
        case .dataCorrupted(let context):
            return "dato corrupto en \(path(context.codingPath)): \(context.debugDescription)"
        @unknown default:
            return error.localizedDescription
        }
    }

    private static func path(_ keys: [CodingKey]) -> String {
        let value = keys.map(\.stringValue).joined(separator: ".")
        return value.isEmpty ? "raíz" : value
    }
}

actor NexusAPIClient {
    var baseURL: URL
    private let session: URLSession

    init(baseURL: URL = URL(string: "http://127.0.0.1:8765")!) {
        self.baseURL = baseURL
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 90
        config.timeoutIntervalForResource = 120
        self.session = URLSession(configuration: config)
    }

    func health() async -> Bool {
        guard let url = URL(string: "/api/health", relativeTo: baseURL) else { return false }
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        do {
            let (_, response) = try await session.data(for: request)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    func fetchNative(persist: Bool) async throws -> NativeSnapshot {
        let path = persist ? "/api/native/refresh" : "/api/native"
        guard let url = URL(string: path, relativeTo: baseURL) else { throw NexusAPIError.badURL }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData)
        request.timeoutInterval = 90
        let (data, response) = try await perform(request, attempts: persist ? 1 : 3)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw NexusAPIError.http(http.statusCode)
        }
        guard !data.isEmpty else { throw NexusAPIError.empty }
        do {
            let decoder = JSONDecoder()
            return try decoder.decode(NativeSnapshot.self, from: data)
        } catch {
            throw NexusAPIError.decoding(error)
        }
    }

    func fetchChart(
        ticker: String,
        interval: NexusChartInterval = .oneDay,
        range: NexusChartRange = .oneYear,
        refresh: Bool = false
    ) async throws -> ChartSeriesPayload {
        let key = ticker.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !key.isEmpty,
              var components = URLComponents(
                url: baseURL.appendingPathComponent("api/native/chart/\(key)"),
                resolvingAgainstBaseURL: false
              ) else {
            throw NexusAPIError.badURL
        }
        components.queryItems = [
            URLQueryItem(name: "interval", value: interval.rawValue),
            URLQueryItem(name: "range", value: range.rawValue),
            URLQueryItem(name: "refresh", value: refresh ? "true" : "false"),
        ]
        guard let url = components.url else { throw NexusAPIError.badURL }
        var request = URLRequest(url: url)
        request.timeoutInterval = 30
        request.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, response) = try await perform(request, attempts: 2)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw NexusAPIError.http(http.statusCode)
        }
        guard !data.isEmpty else { throw NexusAPIError.empty }
        do {
            return try JSONDecoder().decode(ChartSeriesPayload.self, from: data)
        } catch {
            throw NexusAPIError.decoding(error)
        }
    }

    func saveWatchlist(_ tickers: [String]) async throws -> [String] {
        guard let url = URL(string: "/api/native/watchlist", relativeTo: baseURL) else { throw NexusAPIError.badURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 8
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["tickers": tickers])
        let (data, response) = try await session.data(for: request)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw NexusAPIError.http(http.statusCode)
        }
        let payload = try JSONDecoder().decode(WatchlistPayload.self, from: data)
        return payload.watchlist ?? tickers
    }

    func saveSettings(_ settings: NativeSettings) async throws -> NativeSettings {
        guard let url = URL(string: "/api/native/settings", relativeTo: baseURL) else { throw NexusAPIError.badURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 8
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(settings)
        let (data, response) = try await session.data(for: request)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw NexusAPIError.http(http.statusCode)
        }
        let payload = try JSONDecoder().decode(SettingsPayload.self, from: data)
        return payload.settings ?? settings
    }

    /// Reintenta únicamente lecturas ante errores de red o 5xx. Las escrituras
    /// siguen siendo de un solo intento para evitar efectos duplicados.
    private func perform(_ request: URLRequest, attempts: Int) async throws -> (Data, URLResponse) {
        let total = max(1, attempts)
        var lastError: Error?
        for attempt in 0..<total {
            do {
                let result = try await session.data(for: request)
                if let http = result.1 as? HTTPURLResponse,
                   http.statusCode >= 500,
                   attempt + 1 < total {
                    try await Task.sleep(nanoseconds: UInt64(250_000_000 * (attempt + 1)))
                    continue
                }
                return result
            } catch {
                lastError = error
                guard attempt + 1 < total else { throw error }
                try await Task.sleep(nanoseconds: UInt64(250_000_000 * (attempt + 1)))
            }
        }
        throw lastError ?? NexusAPIError.empty
    }
}

private struct WatchlistPayload: Codable {
    let watchlist: [String]?
}

private struct SettingsPayload: Codable {
    let settings: NativeSettings?
}

import Foundation
import OSLog

private let nativeAPILogger = Logger(subsystem: "com.nexus.workstation", category: "NativeAPI")

struct EngineHealth: Decodable {
    let version: String?
    let pid: Int32?
    let codeStale: Bool?

    enum CodingKeys: String, CodingKey {
        case version, pid
        case codeStale = "code_stale"
    }
}

enum NexusAPIError: LocalizedError {
    case badURL
    case http(Int)
    case empty
    case decoding(Error)
    case invalidSnapshot(field: String, reason: String)

    var errorDescription: String? {
        switch self {
        case .badURL: return "URL de API inválida"
        case .http(let code): return "API HTTP \(code)"
        case .empty: return "Respuesta vacía"
        case .decoding(let err): return "JSON: \(Self.describeDecodingError(err))"
        case .invalidSnapshot(let field, let reason): return "JSON: contrato nativo inválido en \(field) (\(reason))"
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
        config.timeoutIntervalForResource = 330
        self.session = URLSession(configuration: config)
    }

    func health() async -> Bool {
        await engineHealth() != nil
    }

    /// Estado del motor que escucha en el puerto, aunque no lo haya lanzado esta app.
    func engineHealth() async -> EngineHealth? {
        guard let url = URL(string: "/api/health", relativeTo: baseURL) else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        do {
            let (data, response) = try await session.data(for: request)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
            return (try? JSONDecoder().decode(EngineHealth.self, from: data))
                ?? EngineHealth(version: nil, pid: nil, codeStale: nil)
        } catch {
            return nil
        }
    }

    func fetchNative(persist: Bool) async throws -> NativeSnapshot {
        let path = persist ? "/api/native/refresh" : "/api/native"
        guard let url = URL(string: path, relativeTo: baseURL) else { throw NexusAPIError.badURL }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData)
        // Tras días sin abrir, la descarga completa de todas las capas ronda 2-3 min.
        request.timeoutInterval = persist ? 300 : 90
        let (data, response) = try await perform(request, attempts: persist ? 1 : 3)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw NexusAPIError.http(http.statusCode)
        }
        guard !data.isEmpty else { throw NexusAPIError.empty }
        return try Self.decodeNativeSnapshot(data)
    }

    static func decodeNativeSnapshot(_ data: Data) throws -> NativeSnapshot {
        let decoder = JSONDecoder()
        let diagnostics = SnapshotDecodingDiagnostics()
        decoder.userInfo[SnapshotDecodingDiagnostics.key] = diagnostics
        let snapshot: NativeSnapshot
        do {
            snapshot = try decoder.decode(NativeSnapshot.self, from: data)
        } catch {
            throw NexusAPIError.decoding(error)
        }
        try validateOperationalSnapshot(snapshot)
        let discardedRows = diagnostics.discardedRows
        if discardedRows > 0 {
            nativeAPILogger.warning("Snapshot parcial: \(discardedRows, privacy: .public) filas descriptivas descartadas.")
        }
        return snapshot
    }

    private static func validateOperationalSnapshot(_ snapshot: NativeSnapshot) throws {
        func invalid(_ field: String, _ reason: String = "campo requerido ausente") -> NexusAPIError {
            .invalidSnapshot(field: field, reason: reason)
        }
        guard snapshot.schema == "nexus.native.v1" else {
            throw invalid("schema", "versión no compatible")
        }
        guard let captured = snapshot.capturedAtUtc,
              ISO8601DateFormatter.nexus.date(from: captured) != nil
                || ISO8601DateFormatter.nexusFractional.date(from: captured) != nil else {
            throw invalid("captured_at_utc", "fecha de captura no válida")
        }
        guard let status = snapshot.status, !status.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw invalid("status")
        }
        guard let action = snapshot.decision?.operationalAction, !action.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw invalid("decision.operational_action")
        }
        guard let calendarBlocks = snapshot.calendar?.shouldBlock else {
            throw invalid("calendar.should_block")
        }
        guard let allowsEntry = snapshot.sessionPlan?.allowsEntry else {
            throw invalid("session_plan.allows_entry")
        }
        // Nunca inferir permiso a partir del texto ni ocultar un bloqueo
        // conocido porque falte la tarjeta que lo explica.
        let isBlocked = calendarBlocks || status.uppercased() == "BLOCKED"
            || snapshot.decision?.operationalPauseReason?.isEmpty == false
        if allowsEntry && (isBlocked || snapshot.blockBanner != nil) {
            throw invalid("session_plan.allows_entry", "contradice un bloqueo activo")
        }
        if isBlocked && snapshot.blockBanner == nil {
            throw invalid("block_banner", "falta el aviso de bloqueo activo")
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

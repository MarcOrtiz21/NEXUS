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

    init(baseURL: URL = URL(string: "http://127.0.0.1:8765")!) {
        self.baseURL = baseURL
    }

    func health() async -> Bool {
        guard let url = URL(string: "/api/health", relativeTo: baseURL) else { return false }
        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    func fetchNative(persist: Bool) async throws -> NativeSnapshot {
        let path = persist ? "/api/native/refresh" : "/api/native"
        guard let url = URL(string: path, relativeTo: baseURL) else { throw NexusAPIError.badURL }
        let (data, response) = try await URLSession.shared.data(from: url)
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
}

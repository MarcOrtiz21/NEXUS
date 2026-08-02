import Foundation
import Combine

@MainActor
final class NexusStore: ObservableObject {
    @Published var snapshot: NativeSnapshot?
    @Published var selected: NavItem = .overview
    @Published var loading = false
    @Published var errorMessage: String?
    @Published var engineStatus: String = "Buscando motor…"
    @Published var autoRefresh = true
    @Published var lastRefresh: Date?
    @Published var selectedAssetKey: String?

    private let client = NexusAPIClient()
    private var engine: EngineProcess?
    private var timer: Timer?
    private var refreshIntervalSeconds: TimeInterval = 300
    private let repoRoot: URL

    init() {
        if let configuredRoot = ProcessInfo.processInfo.environment["NEXUS_ROOT"],
           FileManager.default.fileExists(atPath: configuredRoot) {
            self.repoRoot = URL(fileURLWithPath: configuredRoot, isDirectory: true)
        } else {
            // Desarrollo SwiftPM: native/Sources/NEXUS → repo root = ../../../../
            let thisFile = URL(fileURLWithPath: #filePath)
            self.repoRoot = thisFile
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
        }
        Task { await bootstrap() }
    }

    func bootstrap() async {
        await ensureEngine()
        await refresh(persist: false)
        startTimer()
    }

    func ensureEngine() async {
        if await client.health() {
            engineStatus = "Motor OK · :8765"
            return
        }
        engineStatus = "Arrancando motor Python…"
        let process = EngineProcess(repoRoot: repoRoot)
        do {
            try process.start()
            engine = process
            for _ in 0..<40 {
                try? await Task.sleep(nanoseconds: 250_000_000)
                if await client.health() {
                    engineStatus = "Motor OK · :8765"
                    return
                }
            }
            engineStatus = "Motor no responde en :8765"
            errorMessage = "No se pudo contactar con web_dashboard. Prueba run_dashboard.command."
        } catch {
            engineStatus = "Error al arrancar motor"
            errorMessage = error.localizedDescription
        }
    }

    func refresh(persist: Bool) async {
        loading = true
        defer { loading = false }
        do {
            if !(await client.health()) {
                await ensureEngine()
            }
            let nextSnapshot = try await client.fetchNative(persist: persist)
            snapshot = nextSnapshot
            if let configured = nextSnapshot.settings?.refreshIntervalSeconds,
               (60...3600).contains(configured) {
                let nextInterval = TimeInterval(configured)
                if nextInterval != refreshIntervalSeconds {
                    refreshIntervalSeconds = nextInterval
                    startTimer()
                }
            }
            lastRefresh = Date()
            errorMessage = nil
            engineStatus = "Motor OK · :8765"
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func showAsset(_ ticker: String) {
        selectedAssetKey = ticker
    }

    func closeAssetInspector() {
        selectedAssetKey = nil
    }

    private func startTimer() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: refreshIntervalSeconds, repeats: true) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                guard self.autoRefresh else { return }
                // Conserva series EUR/USD y GLD para los gráficos nativos.
                await self.refresh(persist: true)
            }
        }
    }
}

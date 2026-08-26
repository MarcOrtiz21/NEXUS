import Foundation
import Combine
import SwiftUI

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
    @Published var selectedNewsID: String?
    @Published var watchlist: [String] = []
    @Published var showSettings = false

    private let client = NexusAPIClient()
    private var engine: EngineProcess?
    private var timer: Timer?
    private var refreshTask: Task<Void, Never>?
    private var pendingPersistentRefresh = false
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
        NexusNotificationCenter.shared.configure()
        await ensureEngine()
        await refresh(persist: false)
        startTimer()
    }

    func ensureEngine() async {
        engineStatus = "Arrancando motor Python…"
        engine?.terminate()
        engine = nil
        EngineProcess.terminateListener(port: 8765)
        let process = EngineProcess(repoRoot: repoRoot)
        do {
            try process.start()
            engine = process
            for _ in 0..<80 {
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
        if let current = refreshTask {
            pendingPersistentRefresh = pendingPersistentRefresh || persist
            await current.value
            return
        }
        let task = Task { @MainActor [weak self] in
            guard let self else { return }
            await self.performRefresh(persist: persist)
        }
        refreshTask = task
        await task.value
        refreshTask = nil

        if pendingPersistentRefresh {
            pendingPersistentRefresh = false
            await refresh(persist: true)
        }
    }

    private func performRefresh(persist: Bool) async {
        loading = true
        defer { loading = false }
        do {
            if !(await client.health()) {
                await ensureEngine()
            }
            let previous = snapshot
            let nextSnapshot = try await client.fetchNative(persist: persist)
            NexusNotificationCenter.shared.notifyIfNeeded(previous: previous, current: nextSnapshot)
            var refreshTransaction = Transaction()
            refreshTransaction.disablesAnimations = true
            withTransaction(refreshTransaction) {
                snapshot = nextSnapshot
                watchlist = nextSnapshot.watchlist ?? watchlist
            }
            applyRefreshInterval(nextSnapshot.settings?.refreshIntervalSeconds)
            lastRefresh = Date()
            NotificationCenter.default.post(name: .nexusSnapshotDidRefresh, object: nil)
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

    var hasDismissiblePanel: Bool {
        selectedNewsID != nil || selectedAssetKey != nil
    }

    func closeNewsReader() {
        selectedNewsID = nil
    }

    func dismissFrontPanel() {
        if selectedNewsID != nil {
            selectedNewsID = nil
            return
        }
        closeAssetInspector()
    }

    func isWatched(_ ticker: String) -> Bool {
        watchlist.contains(ticker.uppercased())
    }

    func toggleWatchlist(_ ticker: String) async {
        let key = ticker.uppercased()
        var next = watchlist
        if let index = next.firstIndex(of: key) {
            next.remove(at: index)
        } else if next.count < 8 {
            next.append(key)
        } else {
            errorMessage = "El seguimiento admite como máximo 8 nombres."
            return
        }
        watchlist = next
        do {
            watchlist = try await client.saveWatchlist(next)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func saveSettings(_ settings: NativeSettings) async {
        do {
            let saved = try await client.saveSettings(settings)
            applyRefreshInterval(saved.refreshIntervalSeconds)
            if saved.macosNotifications ?? true {
                NexusNotificationCenter.shared.configure()
            }
            errorMessage = nil
            showSettings = false
            await refresh(persist: false)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func applyRefreshInterval(_ seconds: Int?) {
        guard let configured = seconds, (60...3600).contains(configured) else { return }
        let nextInterval = TimeInterval(configured)
        if nextInterval != refreshIntervalSeconds {
            refreshIntervalSeconds = nextInterval
            startTimer()
        }
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

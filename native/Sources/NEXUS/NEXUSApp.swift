import SwiftUI
import AppKit

@main
struct NEXUSApp: App {
    @StateObject private var store = NexusStore()
    @StateObject private var chartData = ChartDataStore()
    @AppStorage("nexus.app.language") private var languageRaw = AppLanguage.spanish.rawValue

    private var language: AppLanguage {
        AppLanguage(rawValue: languageRaw) ?? .spanish
    }

    var body: some Scene {
        WindowGroup("NEXUS Workstation") {
            ContentView()
                .environmentObject(store)
                .environmentObject(chartData)
                .nexusLanguage(language)
                .frame(minWidth: 820, minHeight: 680)
                .preferredColorScheme(.dark)
                .background(WindowConfigurator())
                .onReceive(NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)) { _ in
                    store.shutdownOwnedEngine()
                }
        }
        .defaultSize(width: 1280, height: 860)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(replacing: .appSettings) {
                Button(L10n.string("Ajustes…", language: language)) { store.showSettings = true }
                    .keyboardShortcut(",", modifiers: [.command])
            }
            CommandGroup(after: .windowArrangement) {
                Menu(language == .spanish ? "Tamaño de ventana" : "Window size") {
                    ForEach([820, 1280, 1440, 1800], id: \.self) { width in
                        Button("\(width) pt") {
                            guard let window = NSApplication.shared.mainWindow else { return }
                            let visible = window.screen?.visibleFrame ?? NSRect(x: 0, y: 0, width: width, height: 1028)
                            window.setContentSize(NSSize(width: min(CGFloat(width), visible.width), height: min(1000, visible.height - 28)))
                            let frame = window.frame
                            window.setFrameOrigin(NSPoint(
                                x: min(max(visible.minX, frame.minX), max(visible.minX, visible.maxX - frame.width)),
                                y: min(max(visible.minY, frame.minY), max(visible.minY, visible.maxY - frame.height))
                            ))
                        }
                    }
                }
                Button(L10n.string("Cerrar panel", language: language)) { store.dismissFrontPanel() }
                    .keyboardShortcut(.escape, modifiers: [])
                    .disabled(!store.hasDismissiblePanel)
            }
            CommandMenu("NEXUS") {
                Button(L10n.string("Actualizar", language: language)) { Task { await store.refresh(persist: true) } }
                    .keyboardShortcut("r", modifiers: [.command])
                Button(L10n.string(
                    store.autoRefresh ? "Desactivar actualización automática" : "Activar actualización automática",
                    language: language
                )) {
                    store.autoRefresh.toggle()
                }
                Button(language == .spanish ? "Guardar vista visible como PNG…" : "Save visible view as PNG…") {
                    WindowCapture.save(page: store.selected.rawValue, english: language != .spanish)
                }
                .keyboardShortcut("s", modifiers: [.command, .shift])
                Divider()
                ForEach([NavItem.overview, .report, .news, .forex, .gold, .rotation, .global, .charts, .watchlist, .history], id: \.self) { item in
                    Button {
                        store.selected = item
                    } label: {
                        Text(L10n.string(item.rawValue, language: language))
                    }
                        .keyboardShortcut(item.shortcut, modifiers: [.command])
                }
            }
        }
    }
}

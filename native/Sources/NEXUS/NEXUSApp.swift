import SwiftUI

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
        }
        .defaultSize(width: 1280, height: 860)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(replacing: .appSettings) {
                Button(L10n.string("Ajustes…", language: language)) { store.showSettings = true }
                    .keyboardShortcut(",", modifiers: [.command])
            }
            CommandGroup(after: .windowArrangement) {
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
                Divider()
                ForEach([NavItem.overview, .news, .forexGold, .rotation, .global, .charts, .watchlist, .history], id: \.self) { item in
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

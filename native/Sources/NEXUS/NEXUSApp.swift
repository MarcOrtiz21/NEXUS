import SwiftUI

@main
struct NEXUSApp: App {
    @StateObject private var store = NexusStore()
    @StateObject private var chartData = ChartDataStore()

    var body: some Scene {
        WindowGroup("NEXUS Workstation") {
            ContentView()
                .environmentObject(store)
                .environmentObject(chartData)
                .frame(minWidth: 820, minHeight: 680)
                .preferredColorScheme(.dark)
                .background(WindowConfigurator())
        }
        .defaultSize(width: 1280, height: 860)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(replacing: .appSettings) {
                Button("Ajustes…") { store.showSettings = true }
                    .keyboardShortcut(",", modifiers: [.command])
            }
            CommandGroup(after: .windowArrangement) {
                Button("Cerrar panel") { store.dismissFrontPanel() }
                    .keyboardShortcut(.escape, modifiers: [])
                    .disabled(!store.hasDismissiblePanel)
            }
            CommandMenu("NEXUS") {
                Button("Actualizar") { Task { await store.refresh(persist: true) } }
                    .keyboardShortcut("r", modifiers: [.command])
                Button(store.autoRefresh ? "Desactivar actualización automática" : "Activar actualización automática") {
                    store.autoRefresh.toggle()
                }
                Divider()
                ForEach([NavItem.overview, .report, .news, .forexGold, .rotation, .global, .charts, .watchlist, .history], id: \.self) { item in
                    Button(item.rawValue) { store.selected = item }
                        .keyboardShortcut(item.shortcut, modifiers: [.command])
                }
            }
        }
    }
}

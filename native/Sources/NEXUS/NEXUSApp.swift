import SwiftUI

@main
struct NEXUSApp: App {
    @StateObject private var store = NexusStore()

    var body: some Scene {
        WindowGroup("NEXUS Workstation") {
            ContentView()
                .environmentObject(store)
                .frame(minWidth: 820, minHeight: 680)
                .preferredColorScheme(.dark)
                .background(WindowConfigurator())
        }
        .defaultSize(width: 1280, height: 860)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandMenu("NEXUS") {
                Button("Actualizar") { Task { await store.refresh(persist: true) } }
                    .keyboardShortcut("r", modifiers: [.command])
                Button(store.autoRefresh ? "Auto-refresh: ON" : "Auto-refresh: OFF") {
                    store.autoRefresh.toggle()
                }
            }
        }
    }
}

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: NexusStore
    @Environment(\.dismiss) private var dismiss

    @State private var refreshIntervalSeconds = 300
    @State private var calendarBlockHours = 6
    @State private var calendarBlocksSignals = true
    @State private var sentimentBlocksSignals = true
    @State private var macosNotifications = true
    @AppStorage("newsBlockCookieBanners") private var newsBlockCookieBanners = true
    @AppStorage("nexus.app.language") private var languageRaw = AppLanguage.spanish.rawValue
    @State private var saving = false

    private let intervalOptions = [
        (60, "1 min"),
        (120, "2 min"),
        (300, "5 min"),
        (600, "10 min"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ajustes")
                        .font(.title2.weight(.bold))
                    Text("Se aplican al siguiente snapshot.")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                }
                Spacer(minLength: 8)
                NexusActionButton(title: "Cancelar") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                NexusActionButton(
                    title: saving ? "Guardando…" : "Guardar y cerrar",
                    role: .prominent,
                    disabled: saving
                ) {
                    Task { await save() }
                }
                .keyboardShortcut(.defaultAction)
            }

            VStack(alignment: .leading, spacing: 8) {
                NexusSectionHeader(title: "Idioma")
                Picker("Idioma de la interfaz", selection: $languageRaw) {
                    ForEach(AppLanguage.allCases) { language in
                        Text(language.displayName).tag(language.rawValue)
                    }
                }
                .pickerStyle(.segmented)
                Text("El cambio se aplica inmediatamente. Los análisis generados por el motor conservan el idioma de origen.")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
            .nexusCard()

            VStack(alignment: .leading, spacing: 8) {
                NexusSectionHeader(title: "Actualización")
                Picker("Intervalo automático", selection: $refreshIntervalSeconds) {
                    ForEach(intervalOptions, id: \.0) { value, label in
                        Text(LocalizedStringKey(label)).tag(value)
                    }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                Toggle("Auto-refresh", isOn: $store.autoRefresh)
            }
            .nexusCard()

            VStack(alignment: .leading, spacing: 8) {
                NexusSectionHeader(title: "Filtros de riesgo")
                Picker("Ventana de calendario", selection: $calendarBlockHours) {
                    Text("3 horas").tag(3)
                    Text("6 horas").tag(6)
                }
                .pickerStyle(.segmented)
                Toggle("Bloquear señales por calendario", isOn: $calendarBlocksSignals)
                Toggle("Bloquear señales por sentimiento extremo", isOn: $sentimentBlocksSignals)
            }
            .nexusCard()

            VStack(alignment: .leading, spacing: 8) {
                NexusSectionHeader(title: "Sistema")
                Toggle("Notificaciones de macOS", isOn: $macosNotifications)
                Toggle("Ocultar avisos de cookies en noticias", isOn: $newsBlockCookieBanners)
                Text("Notifica al cambiar la acción o al bloquear el calendario. El escudo de cookies no corta scripts: Yahoo y The Guardian dejarían de mostrar el artículo.")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .nexusCard()
        }
        .padding(16)
        .frame(minWidth: 440)
        .background(NexusTheme.bg)
        .onAppear(perform: loadFromSnapshot)
    }

    private func loadFromSnapshot() {
        let settings = store.snapshot?.settings
        refreshIntervalSeconds = settings?.refreshIntervalSeconds ?? 300
        calendarBlockHours = settings?.calendarBlockHours == 3 ? 3 : 6
        calendarBlocksSignals = settings?.calendarBlocksSignals ?? true
        sentimentBlocksSignals = settings?.sentimentBlocksSignals ?? true
        macosNotifications = settings?.macosNotifications ?? true
    }

    private func save() async {
        saving = true
        defer { saving = false }
        await store.saveSettings(
            NativeSettings(
                refreshIntervalSeconds: refreshIntervalSeconds,
                calendarBlockHours: calendarBlockHours,
                calendarBlocksSignals: calendarBlocksSignals,
                sentimentBlocksSignals: sentimentBlocksSignals,
                macosNotifications: macosNotifications
            )
        )
    }
}

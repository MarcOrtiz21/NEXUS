import SwiftUI

struct GoldExperimentCard: View {
    let experiment: GoldExperiment?
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            NexusSectionHeader(title: "EXPERIMENTO · TENDENCIA + FRECUENCIA", detail: "seguimiento prospectivo · fuera del score")
            Text(experiment?.methodology ?? "Experimento aún no registrado; no afecta al modelo activo.")
                .font(.caption).foregroundStyle(NexusTheme.muted)
            Text("Registro: \(experiment?.registeredAt.map { String($0.prefix(10)) } ?? "—") · \(statusLabel)")
                .font(.caption.monospacedDigit())
            Text("GLD · cierre \(experiment?.priceAsOf ?? "—") · \(experiment?.priceStatus == "OK" ? "caché actualizada" : "pendiente de actualizar")")
                .font(.caption).foregroundStyle(NexusTheme.muted)
            NexusResponsiveGrid(wideColumns: 2, mediumColumns: 1) {
                ForEach(experiment?.horizons ?? []) { horizon in
                    VStack(alignment: .leading, spacing: 8) {
                        Text("\(horizon.horizonDays ?? 0) SESIONES").font(.caption.weight(.bold)).foregroundStyle(NexusTheme.accent)
                        if let preview = experiment?.preview?.first(where: { $0.horizonDays == horizon.horizonDays }), let probability = preview.probability {
                            NexusKVRow(label: "Vista previa · mezcla 50/50", value: percent(probability))
                            NexusKVRow(label: "Tendencia", value: percent(preview.trend))
                        }
                        NexusKVRow(label: "Frecuencia congelada", value: percent(horizon.baseProbability))
                        NexusKVRow(label: "Emitidas / vencidas", value: "\(horizon.predictions ?? 0) / \(horizon.settled ?? 0)")
                        NexusKVRow(label: "Cortes separados", value: "\(horizon.separatedCuts ?? 0)/30")
                        if let brier = horizon.brierScore {
                            NexusKVRow(label: "Brier prospectivo", value: String(format: "%.4f", brier))
                        } else {
                            Text("Precisión y calibración pendientes de resultados nuevos suficientes.")
                                .font(.caption).foregroundStyle(NexusTheme.warn)
                        }
                    }
                    .font(.caption)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(NexusTheme.cardInner, in: RoundedRectangle(cornerRadius: 10))
                    .accessibilityElement(children: .combine)
                }
            }
            Text(experiment?.captureNote ?? "Registro y capturas manuales; no hay tareas programadas.")
                .font(.caption).foregroundStyle(NexusTheme.muted).fixedSize(horizontal: false, vertical: true)
            Text("La vista previa no es una predicción guardada ni una orden. El experimento nunca eleva automáticamente la confianza.")
                .font(.caption).foregroundStyle(NexusTheme.warn).fixedSize(horizontal: false, vertical: true)
        }.nexusCard()
    }
    private func percent(_ value: Double?) -> String {
        value.map { String(format: "%.1f%%", $0) } ?? "—"
    }
    private var statusLabel: String {
        switch experiment?.status {
        case "SHADOW": return "SEGUIMIENTO EXPERIMENTAL"
        case "RULES_CHANGED": return "BLOQUEADO · REGLAS MODIFICADAS"
        case "PRODUCTION_CHANGED": return "BLOQUEADO · PRODUCCIÓN MODIFICADA"
        case "UNAVAILABLE": return "NO DISPONIBLE"
        default: return "SIN REGISTRAR"
        }
    }
}

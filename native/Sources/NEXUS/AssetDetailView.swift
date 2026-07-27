import SwiftUI

struct AssetDetailView: View {
    @EnvironmentObject private var store: NexusStore
    let ticker: String

    private var score: AssetScore? {
        store.snapshot?.decision?.assetScores?[ticker]
    }

    private var metrics: AssetMetrics? {
        if ticker == "EURUSD" { return store.snapshot?.forex?.EURUSD }
        return store.snapshot?.assets?[ticker]
    }

    private var rotationTheme: RotationTheme? {
        store.snapshot?.rotation?.themes?.first { $0.ticker == ticker }
    }

    private var delta: RankingDelta? {
        store.snapshot?.rankingDelta?[ticker]
            ?? store.snapshot?.assetRanking?.first { $0.ticker == ticker }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(ticker)
                            .font(.title.weight(.bold))
                        Text(score?.label ?? rotationTheme?.theme ?? assetName)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    Spacer()
                    Button {
                        store.closeAssetInspector()
                    } label: {
                        Image(systemName: "xmark")
                    }
                    .buttonStyle(.bordered)
                    .help("Cerrar detalle")
                }

                VStack(alignment: .leading, spacing: 8) {
                    NexusSectionHeader(
                        title: "Fortaleza técnica",
                        help: "Score relativo de 0 a 100. No equivale por sí solo a permiso para operar."
                    )
                    HStack(alignment: .firstTextBaseline) {
                        Text("\(scoreValue)")
                            .font(.system(size: 38, weight: .bold, design: .rounded))
                            .foregroundStyle(scoreColor)
                        Text("/ 100")
                            .foregroundStyle(NexusTheme.muted)
                        Spacer()
                        ToneBadge(tone: actionValue, label: actionValue)
                    }
                    NexusScoreBar(value: Double(scoreValue))
                    if let delta {
                        HStack {
                            Label(deltaText(delta.scoreDelta), systemImage: deltaSymbol(delta.scoreDelta))
                            Spacer()
                            if let rank = delta.rank {
                                Text("Puesto \(rank)\(rankChange(delta))")
                            }
                        }
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(deltaColor(delta.scoreDelta))
                    }
                }
                .nexusCard()

                VStack(alignment: .leading, spacing: 9) {
                    NexusSectionHeader(title: "Datos técnicos")
                    NexusKVRow(label: "Precio", value: number(metrics?.price, digits: ticker == "EURUSD" ? 4 : 2))
                    NexusKVRow(label: "Media 20", value: number(metrics?.ma20, digits: ticker == "EURUSD" ? 4 : 2), help: "Promedio de las últimas 20 sesiones.")
                    NexusKVRow(label: "Media 50", value: number(metrics?.ma50, digits: ticker == "EURUSD" ? 4 : 2), help: "Promedio de las últimas 50 sesiones.")
                    NexusKVRow(label: "Media 200", value: number(metrics?.ma200, digits: ticker == "EURUSD" ? 4 : 2), help: "Referencia de tendencia de largo plazo.")
                    NexusKVRow(label: "Tendencia", value: score?.trend ?? rotationTheme?.trend ?? inferredTrend)
                    MetricBar(label: "Momentum 1 mes", value: score?.momentum1m ?? rotationTheme?.momentum1m ?? metrics?.momentum1m, range: -10...10)
                    MetricBar(label: "Momentum 3 meses", value: score?.momentum3m ?? rotationTheme?.momentum3m ?? metrics?.momentum3m, range: -20...20)
                    NexusKVRow(
                        label: "Volatilidad 20 días",
                        value: formatPct(score?.volatility20d ?? metrics?.volatility20d),
                        help: "Variación anualizada reciente. Una cifra alta implica mayor incertidumbre y menor tamaño prudente."
                    )
                }
                .nexusCard()

                NexusGuidanceCard(
                    doing: guidance.doing,
                    avoiding: guidance.avoiding,
                    changes: guidance.changes
                )

                Text("La fortaleza técnica, la recomendación macro y el permiso operativo son capas distintas. Respeta siempre el bloqueo global aunque este activo tenga un score alto.")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .padding(.horizontal, 4)
            }
            .padding(16)
        }
        .frame(minWidth: 330, idealWidth: 380)
    }

    private var assetName: String {
        switch ticker {
        case "SPY": return "S&P 500"
        case "QQQ": return "Nasdaq 100"
        case "TLT": return "Bonos largos"
        case "GLD": return "Oro"
        case "UUP": return "Dólar"
        case "EURUSD": return "Euro / dólar"
        case "CASH": return "Liquidez"
        default: return ticker
        }
    }

    private var inferredTrend: String {
        guard let price = metrics?.price, let ma50 = metrics?.ma50 else { return "—" }
        return price >= ma50 ? "Sobre MA50" : "Bajo MA50"
    }

    private var scoreColor: Color {
        let value = scoreValue
        if value >= 65 { return NexusTheme.good }
        if value >= 45 { return NexusTheme.warn }
        return NexusTheme.bad
    }

    private var guidance: (doing: String, avoiding: String, changes: String) {
        let action = actionValue.uppercased()
        if action.contains("COMPRAR") {
            return (
                "Vigilar una entrada compatible con la asignación operativa y confirmar que no exista bloqueo global.",
                "No perseguir el precio ni concentrar la cartera solo porque el score sea alto.",
                "Perder tendencia, momentum o caer frente al resto del ranking debilitaría la señal."
            )
        }
        if action.contains("REDUCIR") || action.contains("VENDER") {
            return (
                "Reducir exposición o mantenerlo fuera hasta recuperar fuerza relativa.",
                "No promediar pérdidas basándose únicamente en que el precio parezca barato.",
                "Recuperar MA50 y momentum positivo permitiría reevaluarlo."
            )
        }
        return (
            "Mantenerlo en observación y esperar confirmación de tendencia y momentum.",
            "No abrir por una oscilación aislada ni confundir espera con recomendación negativa.",
            "Una mejora sostenida del score y del puesto en el ranking activaría una nueva evaluación."
        )
    }

    private var scoreValue: Int {
        score?.score ?? rotationTheme?.score.map { Int($0.rounded()) } ?? 0
    }

    private var actionValue: String {
        if let action = score?.action { return action }
        let signal = (rotationTheme?.signal ?? "").lowercased()
        if signal.contains("entrada") || signal.contains("mejora") { return "VIGILAR COMPRA" }
        if signal.contains("corrección") || signal.contains("descanso") { return "EVITAR / REDUCIR" }
        return "ESPERAR"
    }

    private func number(_ value: Double?, digits: Int) -> String {
        guard let value else { return "—" }
        return String(format: "%.\(digits)f", value)
    }

    private func deltaText(_ value: Double?) -> String {
        guard let value else { return "Sin comparación anterior" }
        return "Score \(value >= 0 ? "+" : "")\(String(format: "%.1f", value))"
    }

    private func deltaSymbol(_ value: Double?) -> String {
        guard let value else { return "minus" }
        return value > 0 ? "arrow.up.right" : value < 0 ? "arrow.down.right" : "arrow.right"
    }

    private func deltaColor(_ value: Double?) -> Color {
        guard let value else { return NexusTheme.muted }
        return value > 0 ? NexusTheme.good : value < 0 ? NexusTheme.bad : NexusTheme.muted
    }

    private func rankChange(_ delta: RankingDelta) -> String {
        guard let value = delta.rankDelta, value != 0 else { return "" }
        return value > 0 ? " · sube \(value)" : " · baja \(abs(value))"
    }
}

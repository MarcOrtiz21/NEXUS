import SwiftUI

struct AssetDetailView: View {
    @EnvironmentObject private var store: NexusStore
    let ticker: String

    private var score: AssetScore? {
        store.snapshot?.decision?.assetScores?[ticker]
    }

    private var metrics: AssetMetrics? {
        if ticker == "EURUSD" { return store.snapshot?.forex?.EURUSD }
        if let asset = store.snapshot?.assets?[ticker] { return asset }
        guard let theme = rotationTheme else { return nil }
        return AssetMetrics(
            price: theme.price,
            ma20: theme.ma20,
            ma50: theme.ma50,
            ma200: theme.ma200,
            momentum1m: theme.momentum1m,
            momentum3m: theme.momentum3m,
            volatility20d: theme.volatility20d
        )
    }

    private var rotationTheme: RotationTheme? {
        store.snapshot?.rotation?.themes?.first { $0.ticker == ticker }
    }

    private var delta: RankingDelta? {
        store.snapshot?.rankingDelta?[ticker]
            ?? store.snapshot?.assetRanking?.first { $0.ticker == ticker }
    }

    var body: some View {
        ZStack {
            // El inspector no debe heredar la transparencia de la ventana
            // principal: el contenido que queda detrás reduce el contraste.
            NexusTheme.bg
                .ignoresSafeArea()
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

                if let companies = rotationTheme?.companies, !companies.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        NexusSectionHeader(
                            title: "Empresas del tema",
                            detail: "\(companies.count)",
                            help: "Empresas representativas del tema. Las métricas son informativas y no constituyen una cartera recomendada."
                        )
                        if let represents = rotationTheme?.represents {
                            Text(represents.capitalized)
                                .font(.caption)
                                .foregroundStyle(NexusTheme.muted)
                        }
                        ForEach(companies) { company in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack(alignment: .top, spacing: 10) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(company.name ?? company.ticker ?? "Empresa")
                                            .font(.subheadline.weight(.semibold))
                                            .fixedSize(horizontal: false, vertical: true)
                                        Text(company.ticker ?? "—")
                                            .font(.caption2.monospaced())
                                            .foregroundStyle(NexusTheme.muted)
                                    }
                                    Spacer(minLength: 8)
                                    VStack(alignment: .trailing, spacing: 2) {
                                        Text(number(company.price, digits: 2))
                                            .font(.caption.monospacedDigit().weight(.semibold))
                                        Text("1M \(formatPct(company.momentum1m))")
                                            .font(.caption2)
                                            .foregroundStyle(NexusTheme.muted)
                                    }
                                }
                                if let action = company.action {
                                    HStack {
                                        Spacer()
                                        ToneBadge(tone: action, label: action)
                                    }
                                }
                            }
                            .padding(.vertical, 4)
                            if company.id != companies.last?.id { Divider().opacity(0.10) }
                        }
                    }
                    .nexusCard()
                } else if let names = rotationTheme?.names, !names.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        NexusSectionHeader(title: "Empresas representativas")
                        FlowChips(items: names)
                    }
                    .nexusCard()
                } else {
                    VStack(alignment: .leading, spacing: 6) {
                        NexusSectionHeader(title: "Empresas del tema")
                        Text("El motor no ha recibido todavía el desglose de empresas. Actualiza los datos para cargarlo.")
                            .font(.caption)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    .nexusCard()
                }

                if !relatedNews.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        NexusSectionHeader(
                            title: "Noticias relacionadas",
                            detail: "\(relatedNews.count)",
                            help: "Titulares que mencionan empresas o temas del sector. Coincidencia contextual, no causalidad."
                        )
                        ForEach(relatedNews.prefix(5)) { item in
                            Button {
                                store.selected = .news
                            } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack {
                                        Text(item.source ?? "Fuente")
                                            .font(.caption2.weight(.semibold))
                                            .foregroundStyle(NexusTheme.accent)
                                        Spacer()
                                        ToneBadge(tone: item.tone, label: newsImpact(item.tone))
                                    }
                                    Text(item.title)
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(NexusTheme.text)
                                        .multilineTextAlignment(.leading)
                                        .lineLimit(2)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            if item.id != relatedNews.prefix(5).last?.id {
                                Divider().opacity(0.12)
                            }
                        }
                    }
                    .nexusCard()
                }

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
            .scrollContentBackground(.hidden)
        }
        .background(NexusTheme.bg)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var relatedNews: [NewsItem] {
        let items = store.snapshot?.news?.items ?? []
        let names = (rotationTheme?.names ?? []).map { $0.lowercased() }
        let tickers = (rotationTheme?.companies ?? []).compactMap { $0.ticker?.lowercased() }
        let topics = Set(rotationTheme?.newsTopics ?? [])
        guard !names.isEmpty || !topics.isEmpty else { return [] }
        return items.filter { item in
            let topicHit = !(Set(item.linkedTopics ?? []).isDisjoint(with: topics))
            if topicHit { return true }
            let blob = [item.title, item.summary]
                .compactMap { $0?.lowercased() }
                .joined(separator: " ")
            return names.contains { blob.contains($0) } || tickers.contains { blob.contains($0) }
        }
    }

    private func newsImpact(_ tone: String?) -> String {
        switch (tone ?? "").uppercased() {
        case "GOOD": return "Favorable"
        case "BAD": return "Riesgo"
        default: return "Neutro"
        }
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
        case "EWJ": return "Japón"
        case "FXI": return "China"
        case "AAXJ": return "Asia emergente"
        case "EWY": return "Corea del Sur"
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

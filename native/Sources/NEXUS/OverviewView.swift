import SwiftUI

struct OverviewView: View {
    @EnvironmentObject private var store: NexusStore

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: NexusLayout.spacing) {
                actionCard
                overviewGuidance
                NexusAdaptiveGrid(minimumWidth: 300) {
                    rankingCard
                    macroPulseCard
                }
                NexusAdaptiveGrid(minimumWidth: 300) {
                    comparisonCard
                    allocationCard
                }
                NexusAdaptiveGrid(minimumWidth: 250) {
                    previewCard(
                        title: "ROTACIÓN",
                        headline: store.snapshot?.rotation?.state ?? "Sin lectura",
                        detail: store.snapshot?.rotation?.summary ?? "Sin datos sectoriales.",
                        destination: .rotation
                    )
                    previewCard(
                        title: "FOREX / ORO",
                        headline: store.snapshot?.forex?.signal?.action ?? "Sin señal",
                        detail: "\(store.snapshot?.forex?.signal?.evolution ?? "Sin evolución") · Oro \(formatPct(store.snapshot?.gold?.GLD?.momentum1m)) 1M",
                        destination: .forexGold
                    )
                    previewCard(
                        title: "NOTICIAS",
                        headline: "Sesgo \(store.snapshot?.news?.sentiment?.dominant ?? "neutral")",
                        detail: store.snapshot?.news?.sentiment?.details ?? "Sin titulares analizados.",
                        destination: .news
                    )
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(20)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .scrollBounceBehavior(.basedOnSize)
    }

    private var decision: Decision? { store.snapshot?.decision }

    private var actionCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("ACCIÓN AHORA")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            Text(decision?.operationalAction ?? decision?.action ?? "—")
                .font(.system(size: 36, weight: .bold, design: .rounded))
                .foregroundStyle(actionColor)
            if let pause = decision?.operationalPauseReason, !pause.isEmpty {
                Text(pause)
                    .foregroundStyle(NexusTheme.warn)
            }
            HStack {
                Text(decision?.score.map { "Score \($0)/100" } ?? "Score —/100")
                    .font(.subheadline.weight(.semibold))
                Text("·")
                Text(decision?.confidence ?? "—")
                    .foregroundStyle(NexusTheme.muted)
                Spacer()
                Text(relativeAge(from: store.snapshot?.capturedAtUtc))
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }
            if let score = decision?.score {
                ProgressView(value: Double(score), total: 100)
                    .tint(actionColor)
            } else {
                ProgressView(value: 0, total: 100)
                    .tint(NexusTheme.muted)
                    .opacity(0.35)
            }
            if let favored = decision?.favoredAssets, !favored.isEmpty {
                Text("Favorecidos: \(favored.joined(separator: ", "))")
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }
            if let rationale = decision?.rationale, !rationale.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("POR QUÉ")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(NexusTheme.accent)
                    Text(rationale)
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .nexusCard()
        .frame(minHeight: 235)
    }

    private var overviewGuidance: some View {
        NexusGuidanceCard(
            doing: decision?.operationalAction ?? decision?.action ?? "Esperar una señal operativa válida.",
            avoiding: decision?.operationalPauseReason
                ?? "No actuar contra la asignación recomendada ni decidir por una sola métrica.",
            changes: signalChangeCondition
        )
    }

    private var comparisonCard: some View {
        let vs = store.snapshot?.comparison?.vsYesterday ?? store.snapshot?.comparison?.vsPrevious
        return VStack(alignment: .leading, spacing: 10) {
            Text("VS AYER / ANTERIOR")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            if let vs {
                NexusAdaptiveGrid(minimumWidth: 105, spacing: 8) {
                    metric("Score", formatDelta(vs.scoreDelta))
                    metric("SPY", formatPct(vs.spyPct))
                    metric("Oro", formatPct(vs.gldPct))
                    metric("EURUSD", formatPct(vs.eurusdPct))
                }
                if vs.actionChanged == true {
                    Text("Señal: \(vs.actionFrom ?? "—") → \(vs.actionTo ?? "—")")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(NexusTheme.warn)
                } else {
                    Text("Sin cambio de acción (\(vs.actionTo ?? "—"))")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                }
                Text("Ref: \(vs.previousCapturedAt ?? "—")")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            } else {
                Text("Aún no hay historial suficiente para comparar.")
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
        .nexusSizedCard(NexusLayout.standardCardHeight)
    }

    private var macroPulseCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("PULSO MACRO")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            vixIndicator
            vixScale
            macroRow("Bono 10Y", market("US10Y"), suffix: "%")
            macroRow("Inflación", market("CPI_YoY_Pct"), suffix: "%")
            macroRow("Curva 10Y–2Y", market("Yield_Curve_Spread"), suffix: " pp")
            Text(macroInterpretation)
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
        .nexusCard()
        .nexusSizedCard(NexusLayout.standardCardHeight)
    }

    private var rankingCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("RANKING DE ACTIVOS")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            let ranked = (decision?.assetScores ?? [:]).sorted { ($0.value.score ?? 0) > ($1.value.score ?? 0) }
            ForEach(Array(ranked.prefix(6)), id: \.key) { ticker, asset in
                Button {
                    store.showAsset(ticker)
                } label: {
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(asset.label ?? ticker)
                                .lineLimit(2)
                            Text(rankingMovement(ticker))
                                .font(.system(size: 9, weight: .semibold))
                                .foregroundStyle(rankingMovementColor(ticker))
                        }
                        .frame(minWidth: 112, maxWidth: 150, alignment: .leading)
                        VStack(alignment: .trailing, spacing: 3) {
                            NexusScoreBar(value: asset.score.map(Double.init))
                            Text(asset.action ?? "")
                                .font(.caption2)
                                .foregroundStyle(NexusTheme.muted)
                                .lineLimit(2)
                                .multilineTextAlignment(.trailing)
                        }
                        Image(systemName: "chevron.right")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("Abrir detalle técnico de \(asset.label ?? ticker)")
            }
        }
        .nexusCard()
        .nexusSizedCard(NexusLayout.standardCardHeight)
    }

    private var allocationCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("ASIGNACIÓN OPERATIVA")
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
            let alloc = (decision?.allocation ?? [:]).sorted { $0.value > $1.value }
            ForEach(alloc, id: \.key) { key, value in
                if value > 0 {
                    HStack {
                        Text(key).frame(width: 52, alignment: .leading)
                        ProgressView(value: Double(value), total: 100)
                            .tint(key == "CASH" ? NexusTheme.good : NexusTheme.accent)
                        Text("\(value)%").frame(width: 40, alignment: .trailing)
                    }
                    .font(.caption)
                }
            }
            if let macro = decision?.macroAllocation,
               macro != decision?.allocation {
                Divider().opacity(0.12)
                Text("Visión macro sin bloqueo")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(NexusTheme.warn)
                Text(allocationSummary(macro))
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .nexusCard()
        .nexusSizedCard(NexusLayout.standardCardHeight)
    }

    private func previewCard(title: String, headline: String, detail: String, destination: NavItem) -> some View {
        Button {
            store.selected = destination
        } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(title)
                        .font(.caption.weight(.bold))
                        .foregroundStyle(NexusTheme.accent)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .foregroundStyle(NexusTheme.muted)
                }
                Text(headline)
                    .font(.headline)
                    .foregroundStyle(NexusTheme.text)
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .lineLimit(3)
                Spacer(minLength: 0)
            }
            .nexusCard()
            .nexusSizedCard(NexusLayout.previewCardHeight)
        }
        .buttonStyle(.plain)
    }

    private func macroRow(_ label: String, _ value: Double?, suffix: String) -> some View {
        HStack {
            Text(label).foregroundStyle(NexusTheme.muted)
            Spacer()
            Text(value.map { String(format: "%.2f%@", $0, suffix) } ?? "—")
                .fontWeight(.semibold)
        }
        .font(.caption)
    }

    private var vixIndicator: some View {
        let value = market("VIX")
        return HStack(spacing: 8) {
            Circle()
                .fill(vixColor(value))
                .frame(width: 10, height: 10)
            Text("VIX")
                .foregroundStyle(NexusTheme.muted)
            Spacer()
            Text(vixLabel(value))
                .font(.caption.weight(.bold))
                .foregroundStyle(vixColor(value))
            Text(value.map { String(format: "%.2f", $0) } ?? "—")
                .font(.headline.monospacedDigit())
        }
    }

    private var vixScale: some View {
        HStack(spacing: 0) {
            vixBand("Calma <15", NexusTheme.good)
            vixBand("Normal 15–20", NexusTheme.accent)
            vixBand("Cautela 20–30", NexusTheme.warn)
            vixBand("Estrés >30", NexusTheme.bad)
        }
    }

    private func vixBand(_ label: String, _ color: Color) -> some View {
        Text(label)
            .font(.system(size: 8, weight: .semibold))
            .foregroundStyle(color)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
            .background(color.opacity(0.12))
    }

    private func vixColor(_ value: Double?) -> Color {
        guard let value else { return NexusTheme.muted }
        if value < 15 { return NexusTheme.good }
        if value < 20 { return NexusTheme.accent }
        if value < 30 { return NexusTheme.warn }
        return NexusTheme.bad
    }

    private func vixLabel(_ value: Double?) -> String {
        guard let value else { return "Sin dato" }
        if value < 15 { return "Calma" }
        if value < 20 { return "Normal" }
        if value < 30 { return "Cautela" }
        return "Estrés"
    }

    private func scoreColor(_ score: Int?) -> Color {
        guard let score else { return NexusTheme.muted }
        if score >= 65 { return NexusTheme.good }
        if score >= 45 { return NexusTheme.warn }
        return NexusTheme.bad
    }

    private var signalChangeCondition: String {
        let macro = decision?.macroAction ?? decision?.action ?? "—"
        let operational = decision?.operationalAction ?? decision?.action ?? "—"
        if macro != operational {
            return "La operativa podrá acercarse a «\(macro)» cuando desaparezca el bloqueo y la reevaluación mantenga el score."
        }
        return "Una variación material del score, del riesgo macro o del liderazgo de activos activaría una nueva decisión."
    }

    private func rankingMovement(_ ticker: String) -> String {
        guard let delta = rankingDelta(for: ticker) else { return "sin comparación" }
        if let rankDelta = delta.rankDelta, rankDelta != 0 {
            return rankDelta > 0 ? "↑ \(rankDelta) puestos" : "↓ \(abs(rankDelta)) puestos"
        }
        if let scoreDelta = delta.scoreDelta {
            return "score \(scoreDelta >= 0 ? "+" : "")\(String(format: "%.1f", scoreDelta))"
        }
        return "sin cambio"
    }

    private func rankingMovementColor(_ ticker: String) -> Color {
        guard let delta = rankingDelta(for: ticker) else { return NexusTheme.muted }
        let value = Double(delta.rankDelta ?? 0) + (delta.scoreDelta ?? 0)
        return value > 0 ? NexusTheme.good : value < 0 ? NexusTheme.bad : NexusTheme.muted
    }

    private func rankingDelta(for ticker: String) -> RankingDelta? {
        store.snapshot?.rankingDelta?[ticker]
            ?? store.snapshot?.assetRanking?.first { $0.ticker == ticker }
    }

    private func market(_ key: String) -> Double? {
        store.snapshot?.market?[key]?.value
    }

    private var macroInterpretation: String {
        if let vix = market("VIX"), vix > 25 {
            return "Volatilidad alta: priorizar liquidez y reducir tamaño."
        }
        if let yield = market("US10Y"), yield > 4.5 {
            return "Tipos elevados: presión para activos de larga duración."
        }
        if market("VIX") == nil && market("US10Y") == nil {
            return "Datos macro insuficientes para interpretar el entorno."
        }
        return "Entorno sin estrés extremo; respetar igualmente el bloqueo operativo."
    }

    private func metric(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption2).foregroundStyle(NexusTheme.muted)
            Text(value).font(.headline.monospacedDigit())
        }
    }

    private func allocationSummary(_ allocation: [String: Int]) -> String {
        allocation
            .filter { $0.value > 0 }
            .sorted { $0.value > $1.value }
            .map { "\($0.key) \($0.value)%" }
            .joined(separator: " · ")
    }

    private var actionColor: Color {
        let text = (decision?.operationalAction ?? decision?.action ?? "").uppercased()
        if text.contains("COMPRAR") { return NexusTheme.good }
        if text.contains("VENDER") || text.contains("REDUCIR") { return NexusTheme.bad }
        return NexusTheme.warn
    }
}

struct BlockBannerView: View {
    @EnvironmentObject private var store: NexusStore
    let banner: BlockBanner
    let compact: Bool
    @State private var remaining: Int
    @State private var expanded = false

    init(banner: BlockBanner, compact: Bool = false) {
        self.banner = banner
        self.compact = compact
        _remaining = State(initialValue: banner.countdownSeconds ?? 0)
    }

    var body: some View {
        Group {
            if compact && !expanded {
                compactBody
            } else {
                expandedBody
            }
        }
        .foregroundStyle(.white)
        .padding(compact && !expanded ? 10 : 14)
        .background(
            LinearGradient(
                colors: [NexusTheme.bad.opacity(0.82), Color.orange.opacity(0.66)],
                startPoint: .leading,
                endPoint: .trailing
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .task(id: banner.countdownSeconds) {
            remaining = banner.countdownSeconds ?? 0
            while remaining > 0 && !Task.isCancelled {
                do {
                    try await Task.sleep(nanoseconds: 1_000_000_000)
                    remaining -= 1
                } catch {
                    return
                }
            }
        }
    }

    private var compactBody: some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
            Text(banner.title)
                .font(.subheadline.weight(.bold))
                .lineLimit(1)
            Text("· \(banner.actionHint ?? "ESPERAR")")
                .font(.caption.weight(.semibold))
                .lineLimit(1)
            Spacer()
            if remaining > 0 {
                Text(countdownLabel)
                    .font(.caption.monospacedDigit().weight(.bold))
            }
            Button("Detalle") {
                withAnimation(.easeInOut(duration: 0.18)) { expanded = true }
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .tint(.white)
        }
    }

    private var expandedBody: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                Text(banner.title)
                    .font(.headline)
                Spacer()
                if remaining > 0 {
                    Text(countdownLabel)
                        .font(.caption.monospacedDigit().weight(.bold))
                }
                if compact {
                    Button {
                        withAnimation(.easeInOut(duration: 0.18)) { expanded = false }
                    } label: {
                        Image(systemName: "chevron.up")
                    }
                    .buttonStyle(.plain)
                    .help("Contraer aviso")
                }
            }
            Text(banner.guidance)
                .font(.subheadline)
            if let event = banner.eventTitle {
                Text("Evento: \(event)")
                    .font(.caption)
                    .opacity(0.9)
            }
            Text("Sugerencia: \(banner.actionHint ?? "ESPERAR")")
                .font(.caption.weight(.semibold))
            HStack(spacing: 8) {
                Button("Ver histórico") {
                    store.selected = .history
                }
                .buttonStyle(.bordered)
                .tint(.white)

                Button("Reevaluar") {
                    Task { await store.refresh(persist: true) }
                }
                .buttonStyle(.borderedProminent)
                .tint(.white.opacity(0.24))
                .disabled(store.loading)
            }
            .font(.caption.weight(.semibold))
        }
    }

    private var countdownLabel: String {
        let h = remaining / 3600
        let m = (remaining % 3600) / 60
        let s = remaining % 60
        if h > 0 { return String(format: "%dh %02dm", h, m) }
        return String(format: "%02d:%02d", m, s)
    }

}

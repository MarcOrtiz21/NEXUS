import SwiftUI
import AppKit

struct NexusPage<Content: View>: View {
    var scroll: Bool = true
    @ViewBuilder var content: () -> Content

    var body: some View {
        GeometryReader { proxy in
            let width = max(0, proxy.size.width)
            let breakpoint = NexusBreakpoint.from(width: width)
            Group {
                if scroll {
                    ScrollView {
                        pageBody(width: width)
                    }
                    .scrollBounceBehavior(.basedOnSize)
                } else {
                    pageBody(width: width)
                }
            }
            .environment(\.nexusBreakpoint, breakpoint)
            .environment(\.nexusContentWidth, width)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func pageBody(width: CGFloat) -> some View {
        LazyVStack(alignment: .leading, spacing: NexusLayout.spacing) {
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(NexusLayout.pagePadding)
        .frame(width: width, alignment: .leading)
    }
}

struct NexusResizeHandle: View {
    @Binding var width: CGFloat
    var minWidth: CGFloat = NexusLayout.inspectorMinWidth
    var maxWidth: CGFloat = NexusLayout.inspectorMaxWidth
    @State private var widthAtDragStart: CGFloat?
    @State private var hovering = false

    var body: some View {
        ZStack {
            NexusTheme.border.frame(width: 1)
        }
        .frame(width: 8)
        .frame(maxHeight: .infinity)
        .contentShape(Rectangle())
        .help("Arrastra para cambiar el ancho")
        .onHover { isHovering in
            hovering = isHovering
            if isHovering {
                NSCursor.resizeLeftRight.set()
            } else {
                NSCursor.arrow.set()
            }
        }
        .onDisappear {
            if hovering {
                NSCursor.arrow.set()
            }
        }
        .gesture(
            DragGesture(minimumDistance: 1)
                .onChanged { value in
                    if widthAtDragStart == nil {
                        widthAtDragStart = width
                    }
                    let next = (widthAtDragStart ?? width) - value.translation.width
                    width = min(max(minWidth, next), max(minWidth, maxWidth))
                }
                .onEnded { _ in
                    widthAtDragStart = nil
                }
        )
        .accessibilityLabel("Ancho del panel")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment: width = min(width + 24, maxWidth)
            case .decrement: width = max(width - 24, minWidth)
            default: break
            }
        }
    }
}

struct NexusResponsiveGrid<Content: View>: View {
    @Environment(\.nexusBreakpoint) private var breakpoint
    var wideColumns: Int = 3
    var mediumColumns: Int = 2
    var spacing: CGFloat = NexusLayout.spacing
    let content: Content

    init(
        wideColumns: Int = 3,
        mediumColumns: Int = 2,
        spacing: CGFloat = NexusLayout.spacing,
        @ViewBuilder content: () -> Content
    ) {
        self.wideColumns = wideColumns
        self.mediumColumns = mediumColumns
        self.spacing = spacing
        self.content = content()
    }

    private var columns: Int {
        switch breakpoint {
        case .narrow: return 1
        case .medium: return min(mediumColumns, wideColumns)
        case .wide: return wideColumns
        }
    }

    var body: some View {
        LazyVGrid(
            columns: Array(
                repeating: GridItem(.flexible(minimum: 0), spacing: spacing, alignment: .top),
                count: columns
            ),
            alignment: .leading,
            spacing: spacing
        ) {
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct NexusAdaptiveGrid<Content: View>: View {
    let minimumWidth: CGFloat
    let spacing: CGFloat
    let content: Content

    init(
        minimumWidth: CGFloat = 300,
        spacing: CGFloat = NexusLayout.spacing,
        @ViewBuilder content: () -> Content
    ) {
        self.minimumWidth = minimumWidth
        self.spacing = spacing
        self.content = content()
    }

    var body: some View {
        LazyVGrid(
            columns: [GridItem(.adaptive(minimum: minimumWidth, maximum: .infinity), spacing: spacing, alignment: .top)],
            alignment: .leading,
            spacing: spacing
        ) {
            // No aplicar modificadores al `content` compuesto: SwiftUI lo convertiría
            // en una única celda, superponiendo las tarjetas que entrega el ViewBuilder.
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Rejilla de columnas iguales para filas que deben ocupar todo el ancho.
/// A diferencia de la rejilla adaptativa, no deja una zona vacía cuando hay
/// exactamente dos o tres tarjetas en una pantalla panorámica.
struct NexusEqualGrid<Content: View>: View {
    let columns: Int
    let spacing: CGFloat
    let content: Content

    init(
        columns: Int = 3,
        spacing: CGFloat = NexusLayout.spacing,
        @ViewBuilder content: () -> Content
    ) {
        self.columns = max(1, columns)
        self.spacing = spacing
        self.content = content()
    }

    var body: some View {
        LazyVGrid(
            columns: Array(
                repeating: GridItem(.flexible(minimum: 0), spacing: spacing, alignment: .top),
                count: columns
            ),
            alignment: .leading,
            spacing: spacing
        ) {
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct NexusSectionHeader: View {
    let title: String
    var detail: String? = nil
    var help: String? = nil

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            Text(LocalizedStringKey(title))
                .font(.caption.weight(.bold))
                .foregroundStyle(NexusTheme.accent)
                .textCase(.uppercase)
            if let detail {
                Text(LocalizedStringKey(detail))
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
            if let help {
                Image(systemName: "questionmark.circle")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .help(help)
                    .accessibilityLabel(help)
            }
            Spacer(minLength: 0)
        }
    }
}

struct NexusKVRow: View {
    let label: String
    let value: String
    var tone: Color = NexusTheme.text
    var help: String? = nil

    var body: some View {
        HStack {
            HStack(spacing: 4) {
                Text(LocalizedStringKey(label))
                if let help {
                    Image(systemName: "questionmark.circle")
                        .font(.system(size: 9))
                        .help(help)
                }
            }
            .foregroundStyle(NexusTheme.muted)
            Spacer()
            Text(value)
                .fontWeight(.semibold)
                .foregroundStyle(tone)
                .monospacedDigit()
                .lineLimit(2)
                .multilineTextAlignment(.trailing)
                .fixedSize(horizontal: false, vertical: true)
        }
        .font(.caption)
    }
}

struct NexusSummaryMetricCard: View {
    let title: String
    let value: String
    let hint: String
    var tone: Color = NexusTheme.text
    var help: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            NexusSectionHeader(title: title, help: help)
            Text(value)
                .font(.title2.monospacedDigit().weight(.bold))
                .foregroundStyle(tone)
            Text(hint)
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
                .lineLimit(2)
        }
        .nexusCard()
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }
}

struct NexusStanceCard: View {
    let stance: String
    let buy: String
    let verdict: String
    let doing: String
    let avoiding: String
    var changes: String? = nil
    var help: String? = nil
    var buyLabel: String = "COMPRAR"
    var context: [SessionPlanContext] = []
    var weightCaption: String? = nil
    var legs: [SessionPlanLeg] = []
    var confidence: String? = nil
    var confidenceNote: String? = nil
    var score: Int? = nil
    var scoreDrivers: [ScoreDriver] = []
    var assetScores: [String: AssetScore] = [:]
    var sparklines: [String: [SparklinePoint]] = [:]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            NexusSectionHeader(title: "Qué hacer ahora", help: help)
            HStack(alignment: .top, spacing: 20) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("ACCIÓN")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(NexusTheme.muted)
                    Text(stance)
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .foregroundStyle(NexusTheme.toneColor(stance))
                }
                if let confidence {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("CONFIANZA")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(NexusTheme.muted)
                        Text(confidence)
                            .font(.title3.weight(.bold))
                            .foregroundStyle(NexusTheme.toneColor(confidence))
                    }
                    .frame(minWidth: 88, alignment: .leading)
                }
                if let score {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("SCORE")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(NexusTheme.muted)
                        Text("\(score)/100")
                            .font(.title3.monospacedDigit().weight(.bold))
                            .foregroundStyle(NexusTheme.toneColor(stance))
                    }
                    .frame(minWidth: 76, alignment: .leading)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(buyLabel.uppercased())
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(NexusTheme.muted)
                    Text(buy)
                        .font(.title3.weight(.bold))
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            if let confidenceNote, !confidenceNote.isEmpty {
                Text(confidenceNote)
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !scoreDrivers.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("POR QUÉ ESTE SCORE")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(NexusTheme.muted)
                    ViewThatFits(in: .horizontal) {
                        HStack(alignment: .top, spacing: 8) {
                            ForEach(scoreDrivers.prefix(5)) { driver in
                                scoreDriverCard(driver)
                            }
                        }
                        LazyVGrid(
                            columns: [GridItem(.adaptive(minimum: 160), spacing: 8, alignment: .top)],
                            alignment: .leading,
                            spacing: 8
                        ) {
                            ForEach(scoreDrivers.prefix(5)) { driver in
                                scoreDriverCard(driver)
                            }
                        }
                    }
                }
            }
            if !context.isEmpty {
                HStack(alignment: .top, spacing: 16) {
                    ForEach(context) { item in
                        VStack(alignment: .leading, spacing: 2) {
                            Text((item.label ?? "").uppercased())
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(NexusTheme.muted)
                            Text(item.value ?? "—")
                                .font(.caption.weight(.semibold))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
            if !legs.isEmpty {
                planByAsset
            }
            Text(verdict)
                .font(.subheadline.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
            NexusResponsiveGrid(wideColumns: changes != nil ? 3 : 2, mediumColumns: 1, spacing: 14) {
                stanceColumn("QUÉ HACER", "checkmark.circle.fill", NexusTheme.good, doing)
                stanceColumn("QUÉ EVITAR", "xmark.circle.fill", NexusTheme.bad, avoiding)
                if let changes, !changes.isEmpty {
                    stanceColumn("QUÉ CAMBIARÍA", "arrow.triangle.swap", NexusTheme.warn, changes)
                }
            }
        }
        .nexusCard()
    }

    private func scoreDriverCard(_ driver: ScoreDriver) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 5) {
                Circle()
                    .fill(NexusTheme.accent)
                    .frame(width: 6, height: 6)
                Text(driver.factor ?? "Factor")
                    .font(.caption2.weight(.bold))
                    .lineLimit(1)
            }
            Text(driver.detail ?? "—")
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
                .lineLimit(3)
        }
        .padding(8)
        .frame(minWidth: 110, maxWidth: .infinity, minHeight: 62, maxHeight: 62, alignment: .topLeading)
        .background(NexusTheme.bg.opacity(0.34))
        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
    }

    private var planByAsset: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text("PLAN POR ACTIVO")
                Spacer()
                Text("TÉCNICA")
                    .frame(width: 70, alignment: .trailing)
                Text("AHORA")
                    .frame(width: 72, alignment: .trailing)
                Text("SI SE ABRE")
                    .frame(width: 92, alignment: .trailing)
            }
            .font(.caption2.weight(.bold))
            .foregroundStyle(NexusTheme.muted)
            ForEach(legs) { leg in
                HStack(alignment: .center, spacing: 8) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text(leg.label ?? leg.ticker ?? "Activo")
                            .font(.caption.weight(.semibold))
                        Text(leg.weightNote ?? leg.verb ?? "")
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                            .lineLimit(1)
                    }
                    Spacer(minLength: 8)
                    NexusMiniSparkline(
                        points: sparkline(for: leg),
                        width: 78,
                        height: 26
                    )
                    Text(technicalLabel(for: leg))
                        .font(.caption2.monospacedDigit().weight(.bold))
                        .foregroundStyle(technicalColor(for: leg))
                        .frame(width: 70, alignment: .trailing)
                    Text(leg.now ?? "—")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(NexusTheme.toneColor(leg.now))
                        .frame(width: 72, alignment: .trailing)
                    Text(openColumn(leg))
                        .font(.caption.weight(.semibold))
                        .multilineTextAlignment(.trailing)
                        .frame(width: 92, alignment: .trailing)
                }
            }
            if let weightCaption, !weightCaption.isEmpty {
                Text(weightCaption)
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func assetScore(for leg: SessionPlanLeg) -> (key: String, value: AssetScore)? {
        guard let ticker = leg.ticker?.uppercased() else { return nil }
        guard let value = assetScores[ticker] else { return nil }
        return (ticker, value)
    }

    private var rankedAssets: [Dictionary<String, AssetScore>.Element] {
        assetScores.sorted { ($0.value.score ?? 0) > ($1.value.score ?? 0) }
    }

    private func technicalLabel(for leg: SessionPlanLeg) -> String {
        guard let item = assetScore(for: leg) else { return "—" }
        let rank = rankedAssets.firstIndex(where: { $0.key == item.key }).map { $0 + 1 }
        let score = item.value.score.map(String.init) ?? "—"
        return rank.map { "#\($0) · \(score)" } ?? score
    }

    private func technicalColor(for leg: SessionPlanLeg) -> Color {
        NexusTheme.toneColor(assetScore(for: leg)?.value.action)
    }

    private func sparkline(for leg: SessionPlanLeg) -> [SparklinePoint] {
        guard let ticker = leg.ticker?.uppercased() else { return [] }
        return sparklines[ticker] ?? sparklines["^\(ticker)"] ?? []
    }

    private func openColumn(_ leg: SessionPlanLeg) -> String {
        if leg.kind == "fx" {
            return leg.verb ?? "—"
        }
        if let weight = leg.openWeight {
            return "\(weight)% cartera"
        }
        return "—"
    }

    private func stanceColumn(_ title: String, _ symbol: String, _ tone: Color, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(title, systemImage: symbol)
                .font(.caption.weight(.bold))
                .foregroundStyle(tone)
            Text(text)
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }
}

struct NexusGuidanceCard: View {
    let doing: String
    let avoiding: String
    var changes: String? = nil

    var body: some View {
        NexusResponsiveGrid(wideColumns: changes != nil ? 3 : 2, mediumColumns: 2, spacing: 18) {
            guidance("QUÉ HACER", "checkmark.circle.fill", NexusTheme.good, doing)
            guidance("QUÉ EVITAR", "xmark.circle.fill", NexusTheme.bad, avoiding)
            if let changes, !changes.isEmpty {
                guidance("QUÉ CAMBIARÍA LA SEÑAL", "arrow.triangle.swap", NexusTheme.warn, changes)
            }
        }
        .nexusCard()
    }

    private func guidance(_ title: String, _ symbol: String, _ tone: Color, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(title, systemImage: symbol)
                .font(.caption.weight(.bold))
                .foregroundStyle(tone)
            Text(text)
                .font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }
}

struct NexusNoticeCard: View {
    let title: String
    let detail: String
    var tone: Color = NexusTheme.warn
    var symbol: String = "exclamationmark.triangle.fill"
    var actionTitle: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: symbol)
                .foregroundStyle(tone)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 4) {
                Text(LocalizedStringKey(title))
                    .font(.subheadline.weight(.bold))
                Text(LocalizedStringKey(detail))
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            if let actionTitle, let action {
                NexusActionButton(title: actionTitle, action: action)
            }
        }
        .padding(12)
        .background(tone.opacity(0.14))
        .overlay(
            RoundedRectangle(cornerRadius: NexusLayout.cardRadius, style: .continuous)
                .stroke(tone.opacity(0.35), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: NexusLayout.cardRadius, style: .continuous))
    }
}

struct NexusEmptyState: View {
    let title: String
    let detail: String
    var symbol: String = "tray"

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: symbol)
                .font(.title2)
                .foregroundStyle(NexusTheme.muted)
            Text(LocalizedStringKey(title)).font(.headline)
            Text(LocalizedStringKey(detail))
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 120)
        .nexusCard()
    }
}

struct NexusScoreBar: View {
    let value: Double?
    var range: ClosedRange<Double> = 0...100
    var showValue = true

    var body: some View {
        HStack(spacing: 8) {
            ProgressView(value: clampedValue, total: range.upperBound - range.lowerBound)
                .tint(tone)
            if showValue {
                Text(value.map { String(format: "%.0f", $0) } ?? "—")
                    .font(.caption.monospacedDigit().weight(.bold))
                    .foregroundStyle(tone)
                    .frame(width: 28, alignment: .trailing)
            }
        }
    }

    private var clampedValue: Double {
        guard let value else { return 0 }
        return min(range.upperBound, max(range.lowerBound, value)) - range.lowerBound
    }

    private var tone: Color {
        guard let value else { return NexusTheme.muted }
        let progress = (value - range.lowerBound) / (range.upperBound - range.lowerBound)
        if progress >= 0.65 { return NexusTheme.good }
        if progress >= 0.45 { return NexusTheme.warn }
        return NexusTheme.bad
    }
}

struct NexusMiniSparkline: View {
    let points: [SparklinePoint]
    var width: CGFloat = 88
    var height: CGFloat = 36

    private var samples: [(close: Double, high: Double, low: Double)] {
        Array(points.suffix(42)).compactMap { point in
            guard let close = point.value else { return nil }
            return (close, point.high ?? close, point.low ?? close)
        }
    }

    var body: some View {
        let rows = samples
        Canvas { context, size in
            guard rows.count >= 2 else { return }
            let lows = rows.map(\.low)
            let highs = rows.map(\.high)
            let lo = lows.min() ?? 0
            let hi = highs.max() ?? 1
            let span = max(hi - lo, abs(hi) * 0.001, 0.0001)
            let color = tone(rows)
            let step = size.width / CGFloat(rows.count - 1)
            func y(_ value: Double) -> CGFloat {
                size.height - CGFloat((value - lo) / span) * size.height
            }
            var line = Path()
            var wicks = Path()
            for (index, row) in rows.enumerated() {
                let x = CGFloat(index) * step
                let point = CGPoint(x: x, y: y(row.close))
                if index == 0 { line.move(to: point) } else { line.addLine(to: point) }
                if row.high > row.low {
                    wicks.move(to: CGPoint(x: x, y: y(row.high)))
                    wicks.addLine(to: CGPoint(x: x, y: y(row.low)))
                }
            }
            context.stroke(wicks, with: .color(color.opacity(0.35)), lineWidth: 1)
            context.stroke(line, with: .color(color), lineWidth: 1.3)
        }
        .frame(width: width, height: height)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Tendencia de precio")
        .accessibilityValue(accessibilitySummary(rows))
    }

    private func tone(_ rows: [(close: Double, high: Double, low: Double)]) -> Color {
        guard let first = rows.first?.close, let last = rows.last?.close else { return NexusTheme.muted }
        if last > first { return NexusTheme.good }
        if last < first { return NexusTheme.bad }
        return NexusTheme.muted
    }

    private func accessibilitySummary(
        _ rows: [(close: Double, high: Double, low: Double)]
    ) -> String {
        guard let first = rows.first?.close, let last = rows.last?.close, first != 0 else {
            return "Sin datos suficientes"
        }
        let change = (last / first - 1) * 100
        let direction = change > 0 ? "sube" : (change < 0 ? "baja" : "sin cambio")
        return "\(direction) \(String(format: "%.1f", abs(change))) por ciento en \(rows.count) sesiones"
    }
}

/// Chips fluídos para listar empresas o etiquetas sin forzar una sola fila.
struct FlowChips: View {
    let items: [String]

    var body: some View {
        LazyVGrid(
            columns: [GridItem(.adaptive(minimum: 78), spacing: 6, alignment: .leading)],
            alignment: .leading,
            spacing: 6
        ) {
            ForEach(items, id: \.self) { item in
                Text(item)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(NexusTheme.text)
                    .lineLimit(1)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .frame(maxWidth: .infinity)
                    .background(NexusTheme.cardInner.opacity(0.9))
                    .overlay(
                        Capsule().stroke(.white.opacity(0.10), lineWidth: 1)
                    )
                    .clipShape(Capsule())
            }
        }
    }
}

/// Fila densa de empresa dentro de un tema de rotación.
struct NexusCompanyRow: View {
    let company: RotationCompany
    var compact: Bool = false
    var allowsEntry: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 3 : 6) {
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(company.name ?? company.ticker ?? "Empresa")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(NexusTheme.text)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(company.ticker ?? "—")
                        .font(.caption2.monospaced())
                        .foregroundStyle(NexusTheme.muted)
                }
                Spacer(minLength: 8)
                VStack(alignment: .trailing, spacing: 3) {
                    if let score = company.score {
                        Text("\(score)")
                            .font(.caption.monospacedDigit().weight(.bold))
                            .foregroundStyle(scoreTone(score))
                    }
                    ToneBadge(
                        tone: companyTechnicalTone(company.action, allowsEntry: allowsEntry),
                        label: companyTechnicalLabel(company.action, allowsEntry: allowsEntry)
                    )
                }
            }

            if !compact, company.score != nil {
                NexusScoreBar(value: company.score.map(Double.init), showValue: false)
            }

            if compact {
                Text("1M \(formatPct(company.momentum1m)) · 3M \(formatPct(company.momentum3m))")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            } else {
                HStack(spacing: 0) {
                    metricCell("Precio", number(company.price, digits: 2))
                    metricCell("1M", formatPct(company.momentum1m))
                    metricCell("3M", formatPct(company.momentum3m))
                    metricCell("Tendencia", company.trend ?? "—")
                    metricCell("Vol 20d", formatPct(company.volatility20d))
                }
            }
        }
        .padding(.vertical, compact ? 2 : 5)
        .contentShape(Rectangle())
    }

    private func metricCell(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(LocalizedStringKey(label))
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
            Text(value)
                .font(.caption2.monospacedDigit().weight(.semibold))
                .foregroundStyle(NexusTheme.text)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func scoreTone(_ score: Int) -> Color {
        if score >= 70 { return NexusTheme.good }
        if score >= 45 { return NexusTheme.warn }
        return NexusTheme.bad
    }

    private func number(_ value: Double?, digits: Int) -> String {
        guard let value else { return "—" }
        return String(format: "%.\(digits)f", value)
    }
}

struct NexusKPI: Identifiable {
    var id: String { title }
    let title: String
    let value: String
    var hint: String = ""
    var tone: Color = NexusTheme.text
    var help: String? = nil
}

struct NexusKPIStrip: View {
    let items: [NexusKPI]

    var body: some View {
        NexusResponsiveGrid(wideColumns: min(5, max(1, items.count)), mediumColumns: min(3, max(1, items.count))) {
            ForEach(items) { item in
                VStack(alignment: .leading, spacing: 3) {
                    NexusSectionHeader(title: item.title, help: item.help)
                    Text(item.value)
                        .font(.title3.monospacedDigit().weight(.bold))
                        .foregroundStyle(item.tone)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                    if !item.hint.isEmpty {
                        Text(item.hint)
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.muted)
                            .lineLimit(2)
                    }
                }
                .nexusCard()
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
        }
    }
}

struct NexusSkeleton: View {
    var rows: Int = 3

    var body: some View {
        VStack(alignment: .leading, spacing: NexusLayout.spacing) {
            ForEach(0..<rows, id: \.self) { _ in
                RoundedRectangle(cornerRadius: NexusLayout.cardRadius, style: .continuous)
                    .fill(NexusTheme.card)
                    .frame(maxWidth: .infinity)
                    .frame(height: NexusLayout.metricCardHeight)
            }
        }
        .redacted(reason: .placeholder)
        .accessibilityLabel("Cargando datos")
    }
}

struct NexusMissingSource: View {
    let title: String
    var detail: String = "Actualiza la fuente o espera a la próxima captura."

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "exclamationmark.circle")
                .foregroundStyle(NexusTheme.warn)
            VStack(alignment: .leading, spacing: 2) {
                Text(LocalizedStringKey(title))
                    .font(.caption.weight(.semibold))
                Text(LocalizedStringKey(detail))
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

struct NexusChoicePills<Value: Hashable & Identifiable>: View {
    let values: [Value]
    @Binding var selection: Value
    let title: (Value) -> String
    var helpText: String? = nil

    var body: some View {
        HStack(spacing: 3) {
            ForEach(values) { value in
                let selected = value == selection
                Button {
                    selection = value
                } label: {
                    Text(title(value))
                        .font(.caption.monospacedDigit().weight(.semibold))
                        .foregroundStyle(selected ? Color.white : NexusTheme.muted)
                        .padding(.horizontal, 8)
                        .frame(minHeight: NexusLayout.toolbarButtonSize - 2)
                        .background(
                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                .fill(selected ? NexusTheme.accent : Color.clear)
                        )
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(selected ? .isSelected : [])
                .accessibilityLabel(title(value))
            }
        }
        .padding(2)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(NexusTheme.cardInner)
        )
        .help(helpText ?? "")
        .accessibilityElement(children: .contain)
        .accessibilityLabel(helpText ?? "Selección")
    }
}

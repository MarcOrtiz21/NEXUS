import SwiftUI

private struct FlowEntry: Identifiable, Equatable {
    var id: String { ticker }
    let ticker: String
    let title: String
    let subtitle: String
}

struct ChartsView: View {
    @EnvironmentObject private var store: NexusStore
    @Environment(\.nexusContentWidth) private var contentWidth

    @AppStorage("nexus.terminal.interval") private var intervalRaw = NexusChartInterval.oneDay.rawValue
    @AppStorage("nexus.terminal.range") private var rangeRaw = NexusChartRange.threeMonths.rawValue
    @AppStorage("nexus.terminal.hero") private var heroTicker = "SPY"

    @State private var tickerInput = ""
    @State private var inputError: String?
    @State private var linkedDate: Date?
    @State private var showContext = false

    private let indexTickers = ["SPY", "QQQ", "VIX"]
    private let macroTickers = ["TLT", "GLD", "UUP", "EURUSD"]

    private var interval: NexusChartInterval {
        NexusChartInterval(rawValue: intervalRaw) ?? .oneDay
    }

    private var range: NexusChartRange {
        NexusChartRange(rawValue: rangeRaw) ?? .threeMonths
    }

    private var intervalBinding: Binding<NexusChartInterval> {
        Binding(
            get: { interval },
            set: { intervalRaw = $0.rawValue }
        )
    }

    private var rangeBinding: Binding<NexusChartRange> {
        Binding(
            get: { range },
            set: { rangeRaw = $0.rawValue }
        )
    }

    private var wide: Bool { contentWidth >= 980 }
    private var snapshot: NativeSnapshot? { store.snapshot }

    private var satelliteTickers: [String] {
        let remaining = indexTickers.filter { $0 != heroTicker }
        if remaining.count <= 2 { return remaining }
        var ordered: [String] = []
        if remaining.contains("VIX") { ordered.append("VIX") }
        for ticker in ["SPY", "QQQ"] where remaining.contains(ticker) {
            ordered.append(ticker)
        }
        for ticker in remaining where !ordered.contains(ticker) {
            ordered.append(ticker)
        }
        return Array(ordered.prefix(2))
    }

    private var tapeTickers: [String] {
        unique(indexTickers + [heroTicker] + flowEntries.prefix(3).map(\.ticker))
    }

    private var suggestions: [String] {
        let query = tickerInput.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard query.count >= 1 else { return [] }
        let themes = snapshot?.rotation?.themes ?? []
        let companies = themes.flatMap { $0.companies ?? [] }
        var catalog = unique(
            store.watchlist
                + indexTickers
                + macroTickers
                + flowEntries.map(\.ticker)
                + themes.compactMap(\.ticker)
                + companies.compactMap(\.ticker)
        )
        let nameHits = companies.compactMap { company -> String? in
            guard let ticker = company.ticker else { return nil }
            let name = (company.name ?? "").uppercased()
            return name.contains(query) ? ticker : nil
        }
        catalog = unique(nameHits + catalog)
        return Array(catalog.filter { $0 != heroTicker && ($0.hasPrefix(query) || nameHits.contains($0)) }.prefix(8))
    }

    var body: some View {
        NexusPage {
            terminalHeader
            quoteTape
            marketBoard
            if showContext {
                macroStrip
                flowStrip
            }
        }
        .onAppear(perform: normalizeRange)
        .onChange(of: intervalRaw) { _, _ in
            normalizeRange()
            linkedDate = nil
        }
        .onChange(of: rangeRaw) { _, _ in linkedDate = nil }
        .task {
            guard !showContext else { return }
            try? await Task.sleep(nanoseconds: 220_000_000)
            guard !Task.isCancelled else { return }
            showContext = true
        }
    }

    private var terminalHeader: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                NexusSectionHeader(
                    title: "Terminal de mercados",
                    help: "El panel grande es el foco. Pulsa un satélite o una empresa en flujo para promoverla. El cursor se comparte entre gráficas visibles."
                )
                Spacer(minLength: 8)
                Text(interval.label + " · " + range.label)
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(NexusTheme.muted)
            }

            ViewThatFits(in: .horizontal) {
                HStack(spacing: 10) {
                    globalTimeControls
                    Spacer(minLength: 8)
                    tickerSearch
                }
                VStack(alignment: .leading, spacing: 8) {
                    globalTimeControls
                    tickerSearch
                }
            }

            if let inputError {
                Label(inputError, systemImage: "exclamationmark.triangle")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.warn)
            } else if let state = snapshot?.rotation?.state {
                Text(state)
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                    .lineLimit(2)
            }
        }
        .nexusCard()
    }

    private var globalTimeControls: some View {
        HStack(spacing: 8) {
            HStack(spacing: 6) {
                Text("Velas")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                Picker("Intervalo global", selection: intervalBinding) {
                    ForEach(NexusChartInterval.allCases) { item in
                        Text(item.label).tag(item)
                    }
                }
                .pickerStyle(.menu)
                .labelsHidden()
                .fixedSize()
            }
            .help("Duración de cada vela en todos los paneles.")

            ViewThatFits(in: .horizontal) {
                NexusChoicePills(
                    values: interval.allowedRanges,
                    selection: rangeBinding,
                    title: { $0.label },
                    helpText: "Ventana histórica de todos los paneles."
                )

                Picker("Rango global", selection: rangeBinding) {
                    ForEach(interval.allowedRanges) { item in
                        Text(item.label).tag(item)
                    }
                }
                .pickerStyle(.menu)
                .labelsHidden()
                .fixedSize()
            }

            NexusToolbarButton(
                systemImage: "arrow.counterclockwise",
                label: "Volver a SPY",
                helpText: "Recentrar el panel grande en S&P 500 y sincronizar el cursor."
            ) {
                heroTicker = "SPY"
                linkedDate = nil
                tickerInput = ""
                inputError = nil
            }
        }
    }

    private var tickerSearch: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                TextField("Sustituir foco (SPY, NVDA…)", text: $tickerInput)
                    .textFieldStyle(.roundedBorder)
                    .frame(minWidth: 150, idealWidth: 210, maxWidth: 240)
                    .onSubmit(applySearch)
                NexusToolbarButton(
                    systemImage: "arrow.up.left.and.arrow.down.right",
                    label: "Poner en foco",
                    helpText: "Sustituye el panel grande por este ticker.",
                    prominent: true
                ) {
                    applySearch()
                }
            }
            if !suggestions.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(suggestions, id: \.self) { ticker in
                            Button(ticker) {
                                tickerInput = ticker
                                applySearch()
                            }
                            .buttonStyle(.plain)
                            .font(.caption2.weight(.semibold))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(NexusTheme.cardInner, in: Capsule(style: .continuous))
                        }
                    }
                }
            }
        }
    }

    private var quoteTape: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(tapeTickers, id: \.self) { ticker in
                    quoteChip(ticker)
                }
            }
        }
        .padding(.vertical, 2)
    }

    private func quoteChip(_ ticker: String) -> some View {
        let quote = tapeQuote(ticker)
        let selected = ticker == heroTicker
        return Button {
            focus(ticker)
        } label: {
            HStack(spacing: 6) {
                Text(ticker)
                    .font(.caption2.weight(.bold))
                Text(quote.price)
                    .font(.caption2.monospacedDigit())
                Text(quote.change)
                    .font(.caption2.monospacedDigit().weight(.semibold))
                    .foregroundStyle(quote.tone)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(
                Capsule(style: .continuous)
                    .fill(selected ? NexusTheme.accent.opacity(0.16) : NexusTheme.card)
            )
            .overlay(
                Capsule(style: .continuous)
                    .stroke(selected ? NexusTheme.accent.opacity(0.45) : NexusTheme.border, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .help("Poner \(ticker) en el panel grande")
    }

    private var marketBoard: some View {
        Group {
            if wide {
                HStack(alignment: .top, spacing: NexusLayout.spacing) {
                    chartPanel(heroTicker, title: panelTitle(heroTicker), minHeight: 292, focused: true)
                        .frame(maxWidth: .infinity)
                    VStack(spacing: NexusLayout.spacing) {
                        ForEach(satelliteTickers, id: \.self) { ticker in
                            chartPanel(ticker, title: panelTitle(ticker), minHeight: 136)
                        }
                    }
                    .frame(width: min(360, max(260, contentWidth * 0.32)))
                }
            } else {
                VStack(spacing: NexusLayout.spacing) {
                    chartPanel(heroTicker, title: panelTitle(heroTicker), minHeight: 240, focused: true)
                    HStack(alignment: .top, spacing: NexusLayout.spacing) {
                        ForEach(satelliteTickers, id: \.self) { ticker in
                            chartPanel(ticker, title: panelTitle(ticker), minHeight: 132)
                                .frame(maxWidth: .infinity)
                        }
                    }
                }
            }
        }
    }

    private var macroStrip: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "Macro y defensivos",
                help: "Duración, oro, dólar y euro. Pulsa para promover al panel grande."
            )
            LazyVGrid(
                columns: Array(
                    repeating: GridItem(.flexible(minimum: 210), spacing: NexusLayout.spacing, alignment: .top),
                    count: contentWidth >= 1_100 ? 4 : (contentWidth >= 720 ? 2 : 1)
                ),
                spacing: NexusLayout.spacing
            ) {
                ForEach(macroTickers.filter { $0 != heroTicker }, id: \.self) { ticker in
                    chartPanel(ticker, title: panelTitle(ticker), minHeight: 128)
                }
            }
        }
    }

    private var flowStrip: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                NexusSectionHeader(
                    title: "Entra el flujo",
                    detail: "\(flowEntries.count)",
                    help: "Temas que reciben flujo y empresas FUERTE de esos cestos. Se actualiza con cada evaluación de mercado."
                )
                Spacer(minLength: 8)
                if let summary = snapshot?.rotation?.summary {
                    Text(summary)
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                        .lineLimit(2)
                        .frame(maxWidth: 420, alignment: .trailing)
                }
            }

            if flowEntries.isEmpty {
                NexusEmptyState(
                    title: "Sin receptores claros",
                    detail: "Cuando un tema entre en flujo o una empresa marque FUERTE, aparecerá aquí sola.",
                    symbol: "arrow.up.right"
                )
            } else {
                LazyVGrid(
                    columns: Array(
                        repeating: GridItem(.flexible(minimum: 220), spacing: NexusLayout.spacing, alignment: .top),
                        count: contentWidth >= 1_100 ? 3 : (contentWidth >= 720 ? 2 : 1)
                    ),
                    spacing: NexusLayout.spacing
                ) {
                    ForEach(flowEntries.filter { $0.ticker != heroTicker }) { entry in
                        VStack(alignment: .leading, spacing: 6) {
                            chartPanel(entry.ticker, title: entry.title, minHeight: 132)
                            Text(entry.subtitle)
                                .font(.caption2)
                                .foregroundStyle(NexusTheme.muted)
                                .padding(.horizontal, 4)
                        }
                    }
                }
            }
        }
        .animation(.easeInOut(duration: 0.18), value: flowEntries.map(\.ticker).joined(separator: ","))
    }

    private var flowEntries: [FlowEntry] {
        let reserved = Set(indexTickers + macroTickers)
        var seen = reserved
        var entries: [FlowEntry] = []
        let themes = snapshot?.rotation?.themes ?? []
        let entering = themes
            .filter { theme in
                flowBucket(theme) == "recibiendo" || (theme.leadership ?? "") == "receptor"
            }
            .sorted { ($0.relative1mVsSpy ?? -.infinity) > ($1.relative1mVsSpy ?? -.infinity) }

        for theme in entering.prefix(4) {
            if let ticker = theme.ticker {
                let key = normalizedTicker(ticker)
                if !key.isEmpty, seen.insert(key).inserted {
                    entries.append(FlowEntry(
                        ticker: key,
                        title: theme.theme ?? key,
                        subtitle: "Tema · \(theme.signal ?? "entra flujo")"
                    ))
                }
            }
            let roster = (theme.companies ?? [])
                .sorted { ($0.score ?? 0) > ($1.score ?? 0) }
            let strong = roster.filter { company in
                let action = (company.action ?? "").uppercased()
                return action == "FUERTE" || (company.score ?? 0) >= 70
            }
            let companies = strong.isEmpty ? Array(roster.prefix(1)) : strong
            for company in companies {
                guard let raw = company.ticker else { continue }
                let ticker = normalizedTicker(raw)
                guard !ticker.isEmpty, seen.insert(ticker).inserted else { continue }
                entries.append(FlowEntry(
                    ticker: ticker,
                    title: company.name ?? ticker,
                    subtitle: "\(theme.theme ?? theme.ticker ?? "") · \(company.action ?? "FUERTE")"
                ))
                if entries.count >= 6 { return entries }
            }
        }

        if entries.count < 4 {
            let strongest = themes
                .flatMap { theme in (theme.companies ?? []).map { (theme, $0) } }
                .filter { ($0.1.action ?? "").uppercased() == "FUERTE" }
                .sorted { ($0.1.score ?? 0) > ($1.1.score ?? 0) }
            for (theme, company) in strongest {
                guard let raw = company.ticker else { continue }
                let ticker = normalizedTicker(raw)
                guard !ticker.isEmpty, seen.insert(ticker).inserted else { continue }
                entries.append(FlowEntry(
                    ticker: ticker,
                    title: company.name ?? ticker,
                    subtitle: "\(theme.theme ?? theme.ticker ?? "") · fuerte del mapa"
                ))
                if entries.count >= 6 { break }
            }
        }
        return entries
    }

    private func chartPanel(
        _ ticker: String,
        title: String,
        minHeight: CGFloat,
        focused: Bool = false
    ) -> some View {
        let isFocus = focused || ticker == heroTicker
        return NexusSparklineCard(
            title: title,
            help: "Pulsa para poner \(ticker) en el panel grande. Arrastra para alinear el cursor en todas las gráficas.",
            points: snapshot?.sparklines?[ticker] ?? [],
            showRelative: !["SPY", "VIX", "EURUSD"].contains(ticker),
            minHeight: minHeight,
            valueDigits: ticker == "EURUSD" ? 5 : 2,
            ticker: ticker,
            news: [],
            spyPoints: snapshot?.sparklines?["SPY"] ?? [],
            onTap: { store.showAsset(ticker) },
            synchronizedInterval: interval,
            synchronizedRange: range,
            compactMode: true,
            focused: isFocus,
            sharedSelectedDate: linkedDate,
            preferenceNamespace: "terminal",
            onFocus: { focus(ticker) },
            onSharedSelect: { linkedDate = $0 }
        )
        .id("\(ticker)|\(interval.rawValue)|\(range.rawValue)")
    }

    private func panelTitle(_ ticker: String) -> String {
        switch ticker {
        case "SPY": return "S&P 500 · SPY"
        case "QQQ": return "Nasdaq 100 · QQQ"
        case "VIX": return "Volatilidad · VIX"
        case "TLT": return "Treasuries · TLT"
        case "GLD": return "Oro · GLD"
        case "UUP": return "Dólar · UUP"
        case "EURUSD": return "EUR/USD"
        default:
            if let entry = flowEntries.first(where: { $0.ticker == ticker }) {
                return "\(entry.title) · \(ticker)"
            }
            if let theme = snapshot?.rotation?.themes?.first(where: { $0.ticker == ticker }) {
                return "\(theme.theme ?? ticker) · \(ticker)"
            }
            if let company = snapshot?.rotation?.themes?.flatMap({ $0.companies ?? [] }).first(where: { $0.ticker == ticker }) {
                return "\(company.name ?? ticker) · \(ticker)"
            }
            return ticker
        }
    }

    private func tapeQuote(_ ticker: String) -> (price: String, change: String, tone: Color) {
        let points = snapshot?.sparklines?[ticker] ?? []
        let digits = ticker == "EURUSD" ? 4 : 2
        guard let last = points.last?.value else {
            return ("—", "—", NexusTheme.muted)
        }
        let previous = points.dropLast().last?.value ?? points.first?.value
        let change: Double? = {
            guard let previous, previous != 0 else { return nil }
            return (last / previous - 1) * 100
        }()
        let tone: Color
        if let change {
            tone = change > 0 ? NexusTheme.good : (change < 0 ? NexusTheme.bad : NexusTheme.muted)
        } else {
            tone = NexusTheme.muted
        }
        return (String(format: "%.\(digits)f", last), formatPct(change), tone)
    }

    private func focus(_ ticker: String) {
        heroTicker = ticker
        inputError = nil
    }

    private func applySearch() {
        let candidate = normalizedTicker(tickerInput)
        guard !candidate.isEmpty else {
            inputError = "Introduce un ticker para sustituir el panel grande."
            return
        }
        focus(candidate)
        tickerInput = ""
        inputError = nil
    }

    private func normalizeRange() {
        guard !interval.allowedRanges.contains(range) else { return }
        rangeRaw = (
            interval.allowedRanges.contains(.threeMonths)
                ? NexusChartRange.threeMonths
                : interval.allowedRanges.first ?? .oneMonth
        ).rawValue
    }

    private func flowBucket(_ theme: RotationTheme) -> String {
        let signal = (theme.signal ?? "").lowercased()
        if signal.contains("entrada") || signal.contains("mejora") { return "recibiendo" }
        if signal.contains("corrección") || signal.contains("descanso") { return "perdiendo" }
        return "neutrales"
    }

    private func normalizedTicker(_ raw: String) -> String {
        let allowed = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.^=_-")
        let upper = raw.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        let scalars = upper.unicodeScalars.filter { allowed.contains($0) }
        return String(String.UnicodeScalarView(scalars.prefix(20)))
    }

    private func unique(_ values: [String]) -> [String] {
        var seen = Set<String>()
        return values.compactMap { value in
            let normalized = normalizedTicker(value)
            return normalized.isEmpty || !seen.insert(normalized).inserted ? nil : normalized
        }
    }
}

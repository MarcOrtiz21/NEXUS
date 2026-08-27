import SwiftUI

private struct FlowEntry: Identifiable, Equatable {
    var id: String { ticker }
    let ticker: String
    let title: String
    let subtitle: String
}

private enum TerminalPanelSlot: Equatable {
    case focus
    case upperSide
    case lowerSide
}

struct ChartsView: View {
    @EnvironmentObject private var store: NexusStore
    @Environment(\.nexusContentWidth) private var contentWidth

    @AppStorage("nexus.terminal.interval") private var intervalRaw = NexusChartInterval.oneDay.rawValue
    @AppStorage("nexus.terminal.range") private var rangeRaw = NexusChartRange.threeMonths.rawValue
    @AppStorage("nexus.terminal.hero") private var heroTicker = "SPY"
    @AppStorage("nexus.terminal.side.upper") private var upperSideTicker = "QQQ"
    @AppStorage("nexus.terminal.side.lower") private var lowerSideTicker = "VIX"
    @AppStorage("nexus.terminal.custom.exists") private var hasCustomLayout = false
    @AppStorage("nexus.terminal.custom.hero") private var customHeroTicker = "SPY"
    @AppStorage("nexus.terminal.custom.side.upper") private var customUpperSideTicker = "QQQ"
    @AppStorage("nexus.terminal.custom.side.lower") private var customLowerSideTicker = "VIX"
    @AppStorage("nexus.terminal.custom.interval") private var customIntervalRaw = NexusChartInterval.oneDay.rawValue
    @AppStorage("nexus.terminal.custom.range") private var customRangeRaw = NexusChartRange.threeMonths.rawValue

    @State private var tickerInput = ""
    @State private var inputError: String?
    @State private var linkedDate: Date?
    @State private var showContext = false
    @State private var defaultsResetID = 0
    @State private var layoutSaved = false

    private let indexTickers = ["SPY", "QQQ", "VIX"]
    private let macroTickers = ["TLT", "XAUUSD"]
    private let fxTickers = [
        "USDEUR", "EURUSD", "EURCAD", "USDCAD", "GBPUSD",
        "EURGBP", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD",
    ]

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
        [upperSideTicker, lowerSideTicker]
    }

    private var tapeTickers: [String] {
        unique(indexTickers + [heroTicker] + satelliteTickers + flowEntries.prefix(3).map(\.ticker))
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
                + fxTickers
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
                fxStrip
                macroStrip
                flowStrip
            }
        }
        .onAppear {
            normalizeRange()
            normalizePanelSelection()
        }
        .onChange(of: intervalRaw) { _, _ in
            normalizeRange()
            linkedDate = nil
            layoutSaved = false
        }
        .onChange(of: rangeRaw) { _, _ in
            linkedDate = nil
            layoutSaved = false
        }
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
            catalogNavigator
            panelConfigurationBar

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

    private var catalogNavigator: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                Text("EXPLORAR")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(NexusTheme.muted)

                Menu {
                    Section("Índices y volatilidad") {
                        catalogButton("S&P 500", ticker: "SPY")
                        catalogButton("Nasdaq 100", ticker: "QQQ")
                        catalogButton("VIX", ticker: "VIX")
                    }
                    Section("Macro y divisas") {
                        catalogButton("Bonos largos", ticker: "TLT")
                        catalogButton("Oro", ticker: "XAUUSD")
                    }
                    Section("Euro") {
                        catalogButton("USD/EUR", ticker: "USDEUR")
                        catalogButton("EUR/USD", ticker: "EURUSD")
                        catalogButton("EUR/CAD", ticker: "EURCAD")
                        catalogButton("EUR/GBP", ticker: "EURGBP")
                    }
                    Section("Dólar") {
                        catalogButton("USD/CAD", ticker: "USDCAD")
                        catalogButton("USD/JPY", ticker: "USDJPY")
                        catalogButton("USD/CHF", ticker: "USDCHF")
                    }
                    Section("Libra y Oceanía") {
                        catalogButton("GBP/USD", ticker: "GBPUSD")
                        catalogButton("AUD/USD", ticker: "AUDUSD")
                        catalogButton("NZD/USD", ticker: "NZDUSD")
                    }
                } label: {
                    catalogLabel("Mercados", symbol: "chart.xyaxis.line")
                }

                Menu {
                    ForEach(rotationThemes) { theme in
                        if let ticker = theme.ticker {
                            Button {
                                selectCatalogTicker(ticker)
                            } label: {
                                Text("\(theme.theme ?? ticker) · \(ticker)")
                            }
                        }
                    }
                } label: {
                    catalogLabel("Rotación sectorial", symbol: "square.grid.2x2")
                }

                Menu {
                    ForEach(themesWithCompanies) { theme in
                        Menu(theme.theme ?? theme.ticker ?? "Tema") {
                            ForEach((theme.companies ?? []).sorted { ($0.score ?? 0) > ($1.score ?? 0) }) { company in
                                if let ticker = company.ticker {
                                    Button {
                                        selectCatalogTicker(ticker)
                                    } label: {
                                        Text("\(company.name ?? ticker) · \(ticker)")
                                    }
                                }
                            }
                        }
                    }
                } label: {
                    catalogLabel("Empresas por tema", symbol: "building.2")
                }
                .disabled(themesWithCompanies.isEmpty)

                if !store.watchlist.isEmpty {
                    Menu {
                        ForEach(store.watchlist, id: \.self) { ticker in
                            catalogButton(panelTitle(ticker), ticker: ticker)
                        }
                    } label: {
                        catalogLabel("Seguimiento", symbol: "star")
                    }
                }

                Text("En foco: \(panelTitle(heroTicker))")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(NexusTheme.accent)
                    .padding(.leading, 4)
            }
        }
        .help("Elige un mercado, un tema o una empresa sin escribir su ticker.")
    }

    private var panelConfigurationBar: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 7) {
                panelConfigurationLabel
                panelSelector("Foco", ticker: heroTicker, slot: .focus)
                panelSelector("Lateral 1", ticker: upperSideTicker, slot: .upperSide)
                panelSelector("Lateral 2", ticker: lowerSideTicker, slot: .lowerSide)
                Spacer(minLength: 8)
                customLayoutActions
            }
            VStack(alignment: .leading, spacing: 7) {
                panelConfigurationLabel
                HStack(spacing: 7) {
                    panelSelector("Foco", ticker: heroTicker, slot: .focus)
                    panelSelector("Lateral 1", ticker: upperSideTicker, slot: .upperSide)
                    panelSelector("Lateral 2", ticker: lowerSideTicker, slot: .lowerSide)
                }
                customLayoutActions
            }
        }
    }

    private var panelConfigurationLabel: some View {
        Text("PANELES")
            .font(.caption2.weight(.bold))
            .foregroundStyle(NexusTheme.muted)
    }

    private var customLayoutActions: some View {
        HStack(spacing: 6) {
            NexusActionButton(
                title: layoutSaved ? "Guardada" : "Guardar configuración",
                systemImage: layoutSaved ? "checkmark" : "square.and.arrow.down",
                role: layoutSaved ? .prominent : .secondary,
                helpText: "Guarda los tres paneles, el intervalo y el rango actuales."
            ) {
                saveCustomLayout()
            }
            if hasCustomLayout {
                NexusActionButton(
                    title: "Mi configuración",
                    systemImage: "square.and.arrow.down.on.square",
                    helpText: "Recupera la última configuración guardada."
                ) {
                    loadCustomLayout()
                }
            }
        }
    }

    private func panelSelector(
        _ label: String,
        ticker: String,
        slot: TerminalPanelSlot
    ) -> some View {
        Menu {
            Section("Índices y volatilidad") {
                ForEach(indexTickers, id: \.self) { candidate in
                    panelChoice(candidate, slot: slot)
                }
            }
            Section("Macro y defensivos") {
                ForEach(macroTickers, id: \.self) { candidate in
                    panelChoice(candidate, slot: slot)
                }
            }
            Section("Divisas") {
                ForEach(fxTickers, id: \.self) { candidate in
                    panelChoice(candidate, slot: slot)
                }
            }
            if !store.watchlist.isEmpty {
                Section("Seguimiento") {
                    ForEach(store.watchlist, id: \.self) { candidate in
                        panelChoice(candidate, slot: slot)
                    }
                }
            }
            if !rotationThemes.isEmpty {
                Section("Rotación y empresas") {
                    ForEach(rotationThemes) { theme in
                        if let candidate = theme.ticker {
                            panelChoice(candidate, slot: slot)
                        }
                        ForEach(theme.companies ?? []) { company in
                            if let candidate = company.ticker {
                                panelChoice(candidate, slot: slot)
                            }
                        }
                    }
                }
            }
        } label: {
            HStack(spacing: 5) {
                Text(LocalizedStringKey(label))
                    .foregroundStyle(NexusTheme.muted)
                Text(ticker)
                    .fontWeight(.bold)
                    .foregroundStyle(slot == .focus ? NexusTheme.accent : NexusTheme.text)
                Image(systemName: "chevron.down")
                    .font(.system(size: 8, weight: .bold))
                    .foregroundStyle(NexusTheme.muted)
            }
            .font(.caption2)
            .padding(.horizontal, 8)
            .frame(minHeight: 26)
            .background(NexusTheme.cardInner, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .stroke(NexusTheme.border, lineWidth: 1)
            )
        }
        .menuStyle(.borderlessButton)
        .fixedSize()
        .help("Elige el activo del panel \(label.lowercased()).")
    }

    private func panelChoice(_ ticker: String, slot: TerminalPanelSlot) -> some View {
        let candidate = normalizedTicker(ticker)
        let selected = panelTicker(for: slot) == candidate
        return Button {
            setPanel(slot, ticker: candidate)
        } label: {
            if selected {
                Label(panelTitle(candidate), systemImage: "checkmark")
            } else {
                Text(panelTitle(candidate))
            }
        }
    }

    private var rotationThemes: [RotationTheme] {
        (snapshot?.rotation?.themes ?? []).sorted {
            ($0.theme ?? $0.ticker ?? "") < ($1.theme ?? $1.ticker ?? "")
        }
    }

    private var themesWithCompanies: [RotationTheme] {
        rotationThemes.filter { !($0.companies ?? []).isEmpty }
    }

    private func catalogLabel(_ title: String, symbol: String) -> some View {
        Label(title, systemImage: symbol)
            .font(.caption2.weight(.semibold))
            .foregroundStyle(NexusTheme.text)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background(NexusTheme.cardInner, in: Capsule(style: .continuous))
            .overlay(
                Capsule(style: .continuous)
                    .stroke(NexusTheme.border, lineWidth: 1)
            )
    }

    private func catalogButton(_ title: String, ticker: String) -> some View {
        Button("\(title) · \(ticker)") {
            selectCatalogTicker(ticker)
        }
    }

    private func selectCatalogTicker(_ ticker: String) {
        focus(normalizedTicker(ticker))
        tickerInput = ""
        linkedDate = nil
    }

    private var globalTimeControls: some View {
        HStack(spacing: 8) {
            HStack(spacing: 6) {
                Text("Velas")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                Picker("Intervalo global", selection: intervalBinding) {
                    ForEach(NexusChartInterval.allCases) { item in
                        Text(LocalizedStringKey(item.label)).tag(item)
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
                        Text(LocalizedStringKey(item.label)).tag(item)
                    }
                }
                .pickerStyle(.menu)
                .labelsHidden()
                .fixedSize()
            }

            NexusActionButton(
                title: "Predeterminado",
                systemImage: "arrow.counterclockwise",
                helpText: "Restaurar SPY, velas diarias, tres meses y los indicadores iniciales."
            ) {
                restoreTerminalDefaults()
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
                    .frame(width: max(260, contentWidth * 0.33))
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
                help: "Duración y oro. Pulsa para promover al panel grande."
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

    private var fxStrip: some View {
        VStack(alignment: .leading, spacing: 8) {
            NexusSectionHeader(
                title: "Divisas",
                detail: "\(fxTickers.count)",
                help: "Pares spot de monedas fuertes. USDEUR se calcula como el inverso exacto de EURUSD."
            )
            LazyVGrid(
                columns: Array(
                    repeating: GridItem(.flexible(minimum: 210), spacing: NexusLayout.spacing, alignment: .top),
                    count: contentWidth >= 1_100 ? 4 : (contentWidth >= 720 ? 2 : 1)
                ),
                spacing: NexusLayout.spacing
            ) {
                ForEach(fxTickers.filter { $0 != heroTicker }, id: \.self) { ticker in
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
            help: ticker == "XAUUSD"
                ? "Oro spot (XAUUSD), no el ETF GLD. Pulsa para ponerla en el panel grande."
                : "Pulsa para poner \(ticker) en el panel grande. Arrastra para alinear el cursor en todas las gráficas.",
            points: snapshot?.sparklines?[ticker] ?? [],
            showRelative: !isFXTicker(ticker) && !["SPY", "VIX", "XAUUSD"].contains(ticker),
            minHeight: minHeight,
            valueDigits: valueDigits(for: ticker),
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
            preferencesResetID: defaultsResetID,
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
        case "XAUUSD": return "Oro · XAUUSD"
        case "GLD": return "Oro ETF · GLD"
        case "USDEUR": return "Dólar / euro · USD/EUR"
        case "EURUSD": return "Euro / dólar · EUR/USD"
        case "EURCAD": return "Euro / dólar canadiense · EUR/CAD"
        case "USDCAD": return "Dólar / dólar canadiense · USD/CAD"
        case "GBPUSD": return "Libra / dólar · GBP/USD"
        case "EURGBP": return "Euro / libra · EUR/GBP"
        case "USDJPY": return "Dólar / yen · USD/JPY"
        case "USDCHF": return "Dólar / franco suizo · USD/CHF"
        case "AUDUSD": return "Dólar australiano / dólar · AUD/USD"
        case "NZDUSD": return "Dólar neozelandés / dólar · NZD/USD"
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
        let digits = valueDigits(for: ticker)
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

    private func isFXTicker(_ ticker: String) -> Bool {
        fxTickers.contains(ticker)
    }

    private func valueDigits(for ticker: String) -> Int {
        if ticker == "USDJPY" { return 3 }
        return isFXTicker(ticker) ? 5 : 2
    }

    private func panelTicker(for slot: TerminalPanelSlot) -> String {
        switch slot {
        case .focus: return heroTicker
        case .upperSide: return upperSideTicker
        case .lowerSide: return lowerSideTicker
        }
    }

    private func setPanel(_ slot: TerminalPanelSlot, ticker rawTicker: String) {
        let ticker = normalizedTicker(rawTicker)
        guard !ticker.isEmpty else { return }
        let previous = panelTicker(for: slot)
        guard previous != ticker else { return }

        switch slot {
        case .focus:
            if ticker == upperSideTicker {
                upperSideTicker = previous
            } else if ticker == lowerSideTicker {
                lowerSideTicker = previous
            }
            heroTicker = ticker
        case .upperSide:
            if ticker == heroTicker {
                heroTicker = previous
            } else if ticker == lowerSideTicker {
                lowerSideTicker = previous
            }
            upperSideTicker = ticker
        case .lowerSide:
            if ticker == heroTicker {
                heroTicker = previous
            } else if ticker == upperSideTicker {
                upperSideTicker = previous
            }
            lowerSideTicker = ticker
        }

        linkedDate = nil
        inputError = nil
        layoutSaved = false
    }

    private func focus(_ ticker: String) {
        setPanel(.focus, ticker: ticker)
    }

    private func saveCustomLayout() {
        customHeroTicker = heroTicker
        customUpperSideTicker = upperSideTicker
        customLowerSideTicker = lowerSideTicker
        customIntervalRaw = intervalRaw
        customRangeRaw = rangeRaw
        hasCustomLayout = true
        layoutSaved = true
        Task {
            try? await Task.sleep(nanoseconds: 1_400_000_000)
            guard !Task.isCancelled else { return }
            layoutSaved = false
        }
    }

    private func loadCustomLayout() {
        guard hasCustomLayout else { return }
        heroTicker = normalizedTicker(customHeroTicker)
        upperSideTicker = normalizedTicker(customUpperSideTicker)
        lowerSideTicker = normalizedTicker(customLowerSideTicker)
        intervalRaw = customIntervalRaw
        rangeRaw = customRangeRaw
        normalizePanelSelection()
        normalizeRange()
        linkedDate = nil
        inputError = nil
        layoutSaved = false
    }

    private func normalizePanelSelection() {
        let fallback = unique(
            ["SPY", "QQQ", "VIX"]
                + indexTickers
                + macroTickers
                + fxTickers
                + store.watchlist
                + rotationThemes.compactMap(\.ticker)
        )
        var normalized: [String] = []
        for raw in [heroTicker, upperSideTicker, lowerSideTicker] {
            let candidate = normalizedTicker(raw)
            if !candidate.isEmpty, !normalized.contains(candidate) {
                normalized.append(candidate)
            } else if let replacement = fallback.first(where: { !normalized.contains($0) }) {
                normalized.append(replacement)
            }
        }
        while normalized.count < 3 {
            if let replacement = fallback.first(where: { !normalized.contains($0) }) {
                normalized.append(replacement)
            } else {
                break
            }
        }
        guard normalized.count == 3 else { return }
        heroTicker = normalized[0]
        upperSideTicker = normalized[1]
        lowerSideTicker = normalized[2]
    }

    private func restoreTerminalDefaults() {
        intervalRaw = NexusChartInterval.oneDay.rawValue
        rangeRaw = NexusChartRange.threeMonths.rawValue
        heroTicker = "SPY"
        upperSideTicker = "QQQ"
        lowerSideTicker = "VIX"
        linkedDate = nil
        tickerInput = ""
        inputError = nil
        layoutSaved = false
        defaultsResetID += 1
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

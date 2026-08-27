import AppKit
import SwiftUI

struct NexusSparklineCard: View {
    let title: String
    var help: String? = nil
    let points: [SparklinePoint]
    var showRelative: Bool = true
    var minHeight: CGFloat = 180
    var valueDigits: Int = 2
    var emptyText: String = "La serie se rellenará en la próxima descarga completa de mercado."
    var ticker: String? = nil
    var news: [NewsItem] = []
    var spyPoints: [SparklinePoint] = []
    var onTap: (() -> Void)? = nil
    var onOpenNews: ((NewsItem) -> Void)? = nil
    var synchronizedInterval: NexusChartInterval? = nil
    var synchronizedRange: NexusChartRange? = nil
    var compactMode = false
    var focused = false
    var sharedSelectedDate: Date? = nil
    var preferenceNamespace: String? = nil
    var preferencesResetID = 0
    var synchronizationLocked: Bool? = nil
    var onToggleSynchronization: (() -> Void)? = nil
    var onRemove: (() -> Void)? = nil
    var onFocus: (() -> Void)? = nil
    var onSharedSelect: ((Date?) -> Void)? = nil

    @EnvironmentObject private var chartData: ChartDataStore
    @State private var intervalRaw = NexusChartInterval.oneDay.rawValue
    @State private var rangeRaw = NexusChartRange.threeMonths.rawValue
    @State private var showNews = true
    @State private var showVolume = true
    @State private var showMA20 = true
    @State private var showMA50 = false
    @State private var showMA200 = false
    @State private var styleRaw = NexusChartStyle.candles.rawValue
    @State private var scaleRaw = NexusChartScale.linear.rawValue
    @State private var compareSPY = false
    @State private var showRSI = false
    @State private var showMACD = false
    @State private var selectedDate: Date?
    @State private var selectionPinned = false
    @State private var viewportResetID = 0
    @State private var goLatestID = 0
    @State private var parsed: [CandlePoint] = []
    @State private var parsedBenchmark: [CandlePoint] = []
    @State private var cachedNewsFlags: [CandleNewsFlag] = []
    @State private var parseKey = ""

    private var interval: NexusChartInterval {
        synchronizedInterval ?? NexusChartInterval(rawValue: intervalRaw) ?? .oneDay
    }

    private var range: NexusChartRange {
        synchronizedRange ?? NexusChartRange(rawValue: rangeRaw) ?? .threeMonths
    }

    private var chartStyle: NexusChartStyle {
        NexusChartStyle(rawValue: styleRaw) ?? .candles
    }

    private var chartScale: NexusChartScale {
        NexusChartScale(rawValue: scaleRaw) ?? .linear
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

    private var fingerprint: String {
        if let revision = series.revision {
            return "\(interval.rawValue)|\(range.rawValue)|\(revision)"
        }
        return [
            interval.rawValue,
            range.rawValue,
            "\(series.points.count)",
            series.points.first?.date ?? "",
            series.points.last?.date ?? "",
            "\(series.points.last?.value ?? 0)",
            "\(series.points.last?.high ?? 0)",
            "\(series.points.last?.low ?? 0)",
        ].joined(separator: "|")
    }

    private var series: ChartSeriesState {
        guard let ticker else {
            return ChartSeriesState(
                points: points,
                benchmark: spyPoints,
                interval: interval.rawValue,
                range: range.rawValue
            )
        }
        return chartData.state(
            for: ticker,
            interval: interval,
            range: range,
            fallback: points,
            benchmark: spyPoints
        )
    }

    private var windowedPoints: [CandlePoint] {
        let limit = range.fallbackSessions
        let rows = series.loadedRemote || limit == .max ? parsed : Array(parsed.suffix(limit))
        return rows.count >= 2 ? rows : parsed
    }

    private var windowedBenchmark: [CandlePoint] {
        guard let first = windowedPoints.first?.date,
              let last = windowedPoints.last?.date else { return [] }
        return parsedBenchmark.filter { $0.date >= first && $0.date <= last }
    }

    private var selectedPoint: CandlePoint? {
        guard let selectedDate else { return nil }
        return nearest(in: windowedPoints, to: selectedDate)
    }

    private var newsFlags: [CandleNewsFlag] {
        guard showNews, !news.isEmpty, !windowedPoints.isEmpty else { return [] }
        var buckets: [Date: [NewsItem]] = [:]
        for item in news.prefix(40) {
            guard let published = parseFlexibleDate(item.publishedAt) else { continue }
            let target = interval == .oneDay || interval == .oneWeek ? utcDay(published) : published
            guard let candle = windowedPoints.first(where: { $0.date >= target }),
                  candle.date.timeIntervalSince(target) <= 3 * 86_400 else { continue }
            buckets[candle.date, default: []].append(item)
        }
        return buckets.keys.sorted().suffix(10).compactMap { day in
            guard let candle = windowedPoints.first(where: { $0.date == day }) else { return nil }
            let items = buckets[day] ?? []
            let tones = Set(items.compactMap(\.tone))
            return CandleNewsFlag(
                date: day,
                y: candle.high,
                tone: tones.count == 1 ? tones.first : nil,
                items: items
            )
        }
    }

    private var newsFingerprint: String {
        news.prefix(40).map { "\($0.id)|\($0.publishedAt ?? "")|\($0.tone ?? "")" }
            .joined(separator: ";")
    }

    var body: some View {
        applyLifecycle(to: decoratedCard)
    }

    private var cardStack: some View {
        VStack(alignment: .leading, spacing: compactMode ? 6 : 8) {
            header
            errorBanner
            if !compactMode || focused {
                selectionHUD
            }
            chartContent
        }
    }

    private var decoratedCard: some View {
        cardStack
            .nexusCard()
            .overlay(focusRing)
    }

    @ViewBuilder
    private var errorBanner: some View {
        if let error = series.errorMessage {
            Label(error, systemImage: "exclamationmark.triangle")
                .font(.caption2)
                .foregroundStyle(NexusTheme.warn)
                .lineLimit(2)
        }
    }

    private var focusRing: some View {
        RoundedRectangle(cornerRadius: NexusLayout.cardRadius, style: .continuous)
            .stroke(focused ? NexusTheme.accent.opacity(0.55) : Color.clear, lineWidth: 1.2)
    }

    private func applyLifecycle<Content: View>(to view: Content) -> some View {
        let base = view
            .onAppear(perform: handleAppear)
            .onChange(of: fingerprint) { _, _ in reparseIfNeeded() }
            .onChange(of: intervalRaw) { _, _ in
                normalizeRangeForInterval()
                persistPreferences()
                clearSelection()
                cachedNewsFlags = newsFlags
            }
            .onChange(of: rangeRaw) { _, _ in
                persistPreferences()
                clearSelection()
                cachedNewsFlags = newsFlags
            }
            .onChange(of: showNews) { _, _ in
                persistPreferences()
                cachedNewsFlags = newsFlags
            }
            .onChange(of: newsFingerprint) { _, _ in cachedNewsFlags = newsFlags }
        return applyPreferenceLifecycle(to: base)
    }

    private func applyPreferenceLifecycle<Content: View>(to view: Content) -> some View {
        view
            .onChange(of: showVolume) { _, _ in persistPreferences() }
            .onChange(of: showMA20) { _, _ in persistPreferences() }
            .onChange(of: showMA50) { _, _ in persistPreferences() }
            .onChange(of: showMA200) { _, _ in persistPreferences() }
            .onChange(of: styleRaw) { _, _ in persistPreferences() }
            .onChange(of: scaleRaw) { _, _ in persistPreferences() }
            .onChange(of: compareSPY) { _, enabled in
                if enabled {
                    styleRaw = NexusChartStyle.line.rawValue
                    scaleRaw = NexusChartScale.linear.rawValue
                }
                persistPreferences()
            }
            .onChange(of: showRSI) { _, _ in persistPreferences() }
            .onChange(of: showMACD) { _, _ in persistPreferences() }
            .onChange(of: preferencesResetID) { _, _ in restoreChartDefaults() }
            .onChange(of: sharedSelectedDate) { _, date in
                if selectedDate != date {
                    selectedDate = date
                }
            }
            .task(id: "\(ticker ?? "")|\(interval.rawValue)|\(range.rawValue)") {
                guard let ticker else { return }
                await chartData.load(
                    ticker: ticker,
                    interval: interval,
                    range: range,
                    fallback: points,
                    benchmark: spyPoints
                )
                reparseIfNeeded()
            }
    }

    private func handleAppear() {
        restorePreferences()
        reparseIfNeeded()
        if let sharedSelectedDate {
            selectedDate = sharedSelectedDate
        }
    }

    @ViewBuilder
    private var chartContent: some View {
        if windowedPoints.count >= 2 {
            candlePlot
            if showRSI {
                NexusIndicatorPlot(rows: windowedPoints, kind: .rsi, selectedDate: selectedDate)
            }
            if showMACD {
                NexusIndicatorPlot(rows: windowedPoints, kind: .macd, selectedDate: selectedDate)
            }
            if !compactMode || focused {
                chartCaption
            }
        } else {
            Text(emptyText)
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
        }
    }

    private var candlePlot: some View {
        NexusCandlePlot(
            rows: windowedPoints,
            benchmark: windowedBenchmark,
            selectedDate: selectedDate,
            news: cachedNewsFlags,
            valueDigits: valueDigits,
            interval: interval,
            style: chartStyle,
            scale: chartScale,
            compareNormalized: compareSPY && windowedBenchmark.count >= 2,
            minHeight: minHeight,
            showVolume: showVolume,
            showMA20: showMA20,
            showMA50: showMA50,
            showMA200: showMA200,
            resetID: viewportResetID,
            goLatestID: goLatestID,
            onSelect: { date in
                if selectedDate != date {
                    selectedDate = date
                }
                onSharedSelect?(date)
            },
            onPinChange: { selectionPinned = $0 },
            onClearSelection: {
                selectedDate = nil
                selectionPinned = false
                onSharedSelect?(nil)
            }
        )
    }

    private func reparseIfNeeded() {
        guard fingerprint != parseKey else { return }
        parseKey = fingerprint
        parsed = CandlePoint.parse(series.points)
        parsedBenchmark = CandlePoint.parse(series.benchmark)
        cachedNewsFlags = newsFlags
    }

    private var preferencesKey: String {
        let key = (ticker ?? title)
            .uppercased()
            .replacingOccurrences(of: "[^A-Z0-9]+", with: "-", options: .regularExpression)
        let scope = preferenceNamespace.map { ".\($0)" } ?? ""
        return "nexus.chart\(scope).\(key)"
    }

    private func restorePreferences() {
        let defaults = UserDefaults.standard
        if let savedInterval = defaults.string(forKey: "\(preferencesKey).interval"),
           NexusChartInterval(rawValue: savedInterval) != nil {
            intervalRaw = savedInterval
        }
        if let savedRange = defaults.string(forKey: "\(preferencesKey).range"),
           NexusChartRange(rawValue: savedRange) != nil {
            rangeRaw = savedRange
        }
        showNews = defaults.object(forKey: "\(preferencesKey).news") as? Bool ?? !compactMode
        showVolume = defaults.object(forKey: "\(preferencesKey).volume") as? Bool ?? true
        showMA20 = defaults.object(forKey: "\(preferencesKey).ma20") as? Bool ?? true
        showMA50 = defaults.object(forKey: "\(preferencesKey).ma50") as? Bool ?? false
        showMA200 = defaults.object(forKey: "\(preferencesKey).ma200") as? Bool ?? false
        styleRaw = defaults.string(forKey: "\(preferencesKey).style") ?? NexusChartStyle.candles.rawValue
        scaleRaw = defaults.string(forKey: "\(preferencesKey).scale") ?? NexusChartScale.linear.rawValue
        compareSPY = defaults.object(forKey: "\(preferencesKey).compareSPY") as? Bool ?? false
        showRSI = defaults.object(forKey: "\(preferencesKey).rsi") as? Bool ?? false
        showMACD = defaults.object(forKey: "\(preferencesKey).macd") as? Bool ?? false
        normalizeRangeForInterval()
    }

    private func persistPreferences() {
        let defaults = UserDefaults.standard
        defaults.set(intervalRaw, forKey: "\(preferencesKey).interval")
        defaults.set(rangeRaw, forKey: "\(preferencesKey).range")
        defaults.set(showNews, forKey: "\(preferencesKey).news")
        defaults.set(showVolume, forKey: "\(preferencesKey).volume")
        defaults.set(showMA20, forKey: "\(preferencesKey).ma20")
        defaults.set(showMA50, forKey: "\(preferencesKey).ma50")
        defaults.set(showMA200, forKey: "\(preferencesKey).ma200")
        defaults.set(styleRaw, forKey: "\(preferencesKey).style")
        defaults.set(scaleRaw, forKey: "\(preferencesKey).scale")
        defaults.set(compareSPY, forKey: "\(preferencesKey).compareSPY")
        defaults.set(showRSI, forKey: "\(preferencesKey).rsi")
        defaults.set(showMACD, forKey: "\(preferencesKey).macd")
    }

    private func restoreChartDefaults() {
        showNews = !compactMode
        showVolume = true
        showMA20 = true
        showMA50 = false
        showMA200 = false
        styleRaw = NexusChartStyle.candles.rawValue
        scaleRaw = NexusChartScale.linear.rawValue
        compareSPY = false
        showRSI = false
        showMACD = false
        viewportResetID += 1
        clearSelection()
        persistPreferences()
    }

    private func normalizeRangeForInterval() {
        guard !interval.allowedRanges.contains(range) else { return }
        let preferred: NexusChartRange = interval.allowedRanges.contains(.threeMonths)
            ? .threeMonths
            : interval.allowedRanges.first ?? .oneMonth
        rangeRaw = preferred.rawValue
    }

    private func clearSelection() {
        selectedDate = nil
        selectionPinned = false
        viewportResetID += 1
    }

    @ViewBuilder
    private var header: some View {
        if compactMode {
            terminalHeader
        } else {
            VStack(alignment: .leading, spacing: 8) {
                ViewThatFits(in: .horizontal) {
                    titleRow
                    VStack(alignment: .leading, spacing: 6) {
                        NexusSectionHeader(title: title, help: help)
                        HStack {
                            highlightedPrice
                            Spacer(minLength: 8)
                            assetDetailButton
                        }
                    }
                }
                if synchronizedInterval == nil || synchronizedRange == nil {
                    chartRangeControls
                }
                HStack(spacing: 8) {
                    loadingOrRetry
                    Spacer(minLength: 8)
                    chartActions
                }
            }
        }
    }

    private var terminalHeader: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 1) {
                Text(LocalizedStringKey(title))
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                if focused {
                    Text("En foco")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.accent)
                }
            }
            .contentShape(Rectangle())
            .onTapGesture { onFocus?() }
            Spacer(minLength: 6)
            if focused, let onTap {
                NexusToolbarButton(
                    systemImage: "sidebar.right",
                    label: "Ficha",
                    helpText: "Abrir el detalle del activo"
                ) {
                    onTap()
                }
            }
            if series.loading {
                ProgressView().controlSize(.mini)
            }
            chartSettingsMenu
            compactQuote
        }
        .help(help ?? title)
    }

    @ViewBuilder
    private var compactQuote: some View {
        if let highlighted = selectedPoint ?? parsed.last {
            compactQuoteLabel(highlighted)
        }
    }

    private func compactQuoteLabel(_ highlighted: CandlePoint) -> some View {
        let first = windowedPoints.first
        let change: Double? = {
            guard let first, first.close != 0 else { return nil }
            return (highlighted.close / first.close - 1) * 100
        }()
        return VStack(alignment: .trailing, spacing: 1) {
            Text(priceText(highlighted.close))
                .font(.caption.monospacedDigit().weight(.bold))
                .foregroundStyle(highlighted.bullish ? NexusTheme.good : NexusTheme.bad)
            Text(formatPct(change))
                .font(.caption2.monospacedDigit())
                .foregroundStyle((change ?? 0) >= 0 ? NexusTheme.good : NexusTheme.bad)
        }
        .contentShape(Rectangle())
        .onTapGesture { onFocus?() }
    }

    private var titleRow: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            NexusSectionHeader(title: title, help: help)
            Spacer(minLength: 8)
            highlightedPrice
            assetDetailButton
        }
    }

    @ViewBuilder
    private var highlightedPrice: some View {
        if let highlighted = selectedPoint ?? parsed.last {
            Text(priceText(highlighted.close))
                .font(.caption.monospacedDigit().weight(.bold))
                .foregroundStyle(highlighted.bullish ? NexusTheme.good : NexusTheme.bad)
        }
    }

    @ViewBuilder
    private var assetDetailButton: some View {
        if let onTap {
            NexusActionButton(
                title: "Ficha",
                systemImage: "sidebar.right",
                helpText: "Abrir el detalle del activo",
                action: onTap
            )
        }
    }

    private var chartRangeControls: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 8) {
                HStack(spacing: 6) {
                    Text("Velas")
                        .font(.caption2)
                        .foregroundStyle(NexusTheme.muted)
                    intervalPicker
                }
                .help("Duración de cada vela. El menú muestra el intervalo activo.")

                NexusChoicePills(
                    values: interval.allowedRanges,
                    selection: rangeBinding,
                    title: { $0.label },
                    helpText: "Ventana histórica independiente del intervalo de cada vela."
                )
            }
            HStack(spacing: 8) {
                Text("Velas")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                intervalPicker
                Text("Rango")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                rangePicker
                Spacer(minLength: 0)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var intervalPicker: some View {
        Picker("Intervalo", selection: intervalBinding) {
            ForEach(NexusChartInterval.allCases) { item in
                Text(LocalizedStringKey(item.label)).tag(item)
            }
        }
        .pickerStyle(.menu)
        .labelsHidden()
        .fixedSize()
    }

    private var rangePicker: some View {
        Picker("Rango", selection: rangeBinding) {
            ForEach(interval.allowedRanges) { item in
                Text(LocalizedStringKey(item.label)).tag(item)
            }
        }
        .pickerStyle(.menu)
        .labelsHidden()
        .fixedSize()
        .help("Ventana histórica independiente del intervalo de cada vela.")
    }

    @ViewBuilder
    private var loadingOrRetry: some View {
        if series.loading {
            HStack(spacing: 5) {
                ProgressView().controlSize(.small)
                Text("Cargando")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
            .help("Cargando la serie completa sin bloquear el snapshot general.")
        } else if series.errorMessage != nil, let ticker {
            NexusToolbarButton(
                systemImage: "arrow.clockwise",
                label: "Reintentar serie",
                helpText: series.errorMessage ?? "No se pudo cargar la serie."
            ) {
                Task {
                    await chartData.retry(
                        ticker: ticker,
                        interval: interval,
                        range: range,
                        fallback: points,
                        benchmark: spyPoints
                    )
                }
            }
        }
    }

    private var chartActions: some View {
        ViewThatFits(in: .horizontal) {
            fullChartActions
            compactChartActions
        }
    }

    private var fullChartActions: some View {
        HStack(spacing: 6) {
            if let synchronizationLocked, let onToggleSynchronization {
                NexusToolbarButton(
                    systemImage: synchronizationLocked ? "link" : "link.badge.plus",
                    label: synchronizationLocked ? "Usar controles propios" : "Sincronizar con la terminal",
                    helpText: synchronizationLocked
                        ? "Este panel usa el intervalo y rango globales."
                        : "Este panel conserva intervalo y rango propios.",
                    prominent: synchronizationLocked
                ) {
                    onToggleSynchronization()
                }
            }

            chartSettingsMenu

            NexusToolbarButton(
                systemImage: "arrow.right.to.line",
                label: "Ir a la última vela",
                helpText: "Conservar el zoom y volver al dato más reciente.",
                prominent: false
            ) {
                goLatestID += 1
            }

            NexusToolbarButton(
                systemImage: "scope",
                label: "Restablecer gráfico",
                helpText: "Restablecer zoom y volver a la última vela.",
                prominent: false
            ) {
                viewportResetID += 1
            }

            NexusToolbarButton(
                systemImage: showNews ? "newspaper.fill" : "newspaper",
                label: showNews ? "Ocultar noticias" : "Mostrar noticias",
                helpText: showNews
                    ? "Ocultar marcas de titulares sobre el gráfico."
                    : "Marcar en el gráfico los titulares ligados a este activo.",
                prominent: showNews
            ) {
                showNews.toggle()
            }

            if let onRemove {
                NexusToolbarButton(
                    systemImage: "xmark",
                    label: "Quitar panel",
                    helpText: "Quitar este ticker de la terminal."
                ) {
                    onRemove()
                }
            }
        }
        .fixedSize(horizontal: true, vertical: false)
    }

    private var compactChartActions: some View {
        HStack(spacing: 6) {
            chartSettingsMenu
            NexusToolbarButton(
                systemImage: "arrow.right.to.line",
                label: "Ir a la última vela",
                helpText: "Conservar el zoom y volver al dato más reciente."
            ) {
                goLatestID += 1
            }
            Menu {
                Button("Restablecer gráfico", systemImage: "scope") {
                    viewportResetID += 1
                }
                Button(showNews ? "Ocultar noticias" : "Mostrar noticias", systemImage: "newspaper") {
                    showNews.toggle()
                }
                if let onRemove {
                    Divider()
                    Button("Quitar panel", systemImage: "xmark", role: .destructive) {
                        onRemove()
                    }
                }
            } label: {
                Image(systemName: "ellipsis")
                    .frame(width: 20, height: 20)
            }
            .menuStyle(.borderlessButton)
            .help("Más acciones del gráfico")
        }
        .fixedSize(horizontal: true, vertical: false)
    }

    private var chartSettingsMenu: some View {
        Menu {
            Picker("Tipo de gráfica", selection: $styleRaw) {
                ForEach(NexusChartStyle.allCases) { style in
                    Text(LocalizedStringKey(style.label)).tag(style.rawValue)
                }
            }
            Picker("Escala", selection: $scaleRaw) {
                ForEach(NexusChartScale.allCases) { scale in
                    Text(LocalizedStringKey(scale.label)).tag(scale.rawValue)
                }
            }
            Divider()
            Toggle("Comparar con SPY (base 100)", isOn: $compareSPY)
                .disabled((ticker ?? "").uppercased() == "SPY")
            Divider()
            Toggle("Volumen", isOn: $showVolume)
            Toggle("MA20", isOn: $showMA20)
            Toggle("MA50", isOn: $showMA50)
            Toggle("MA200", isOn: $showMA200)
            Divider()
            Toggle("RSI 14", isOn: $showRSI)
            Toggle("MACD 12/26/9", isOn: $showMACD)
        } label: {
            Image(systemName: "function")
                .frame(width: 20, height: 20)
        }
        .menuStyle(.borderlessButton)
        .help("Tipo de gráfica, escala e indicadores técnicos.")
        .accessibilityLabel("Configurar gráfica e indicadores")
    }

    @ViewBuilder
    private var selectionHUD: some View {
        if let highlighted = selectedPoint ?? windowedPoints.last {
            let newsForDay = selectedPoint.flatMap { selected in
                cachedNewsFlags.first(where: { $0.date == selected.date })?.items
            } ?? []
            let delta = highlighted.open == 0
                ? 0
                : (highlighted.close / highlighted.open - 1) * 100
            VStack(alignment: .leading, spacing: 4) {
                ViewThatFits(in: .horizontal) {
                    ohlcvWide(highlighted, delta: delta)
                    ohlcvCompact(highlighted, delta: delta)
                }
                if !newsForDay.isEmpty {
                    ForEach(newsForDay.prefix(3)) { item in
                        if let onOpenNews {
                            Button {
                                onOpenNews(item)
                            } label: {
                                newsRow(item)
                            }
                            .buttonStyle(.plain)
                        } else {
                            newsRow(item)
                        }
                    }
                }
            }
            .padding(8)
            .frame(minHeight: 34)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(NexusTheme.cardInner)
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        } else {
            Text(series.loading ? "Cargando serie…" : "Sin velas para el intervalo y rango seleccionados.")
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
                .frame(minHeight: 34)
        }
    }

    private func ohlcvWide(_ point: CandlePoint, delta: Double) -> some View {
        LazyVGrid(
            columns: [GridItem(.adaptive(minimum: 72), spacing: 8, alignment: .leading)],
            alignment: .leading,
            spacing: 4
        ) {
            selectionMarker
            Text(selectionDateText(point.date))
                .font(.caption.weight(.semibold))
            Text("O \(priceText(point.open))")
            Text("H \(priceText(point.high))")
            Text("L \(priceText(point.low))")
            Text("C \(priceText(point.close))")
                .foregroundStyle(point.bullish ? NexusTheme.good : NexusTheme.bad)
            Text("Δ \(formatPct(delta))")
            Text("Vol \(volumeText(point.volume))")
            Spacer(minLength: 0)
        }
        .font(.caption2.monospacedDigit())
        .foregroundStyle(NexusTheme.muted)
    }

    private func ohlcvCompact(_ point: CandlePoint, delta: Double) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                selectionMarker
                Text(selectionDateText(point.date))
                    .font(.caption.weight(.semibold))
                Spacer(minLength: 4)
                Text("Δ \(formatPct(delta))")
            }
            LazyVGrid(
                columns: [GridItem(.adaptive(minimum: 66), spacing: 6, alignment: .leading)],
                alignment: .leading,
                spacing: 4
            ) {
                ohlcvMetric("O", priceText(point.open))
                ohlcvMetric("H", priceText(point.high))
                ohlcvMetric("L", priceText(point.low))
                ohlcvMetric("C", priceText(point.close), tone: point.bullish ? NexusTheme.good : NexusTheme.bad)
                ohlcvMetric("Vol", volumeText(point.volume))
            }
        }
        .font(.caption2.monospacedDigit())
        .foregroundStyle(NexusTheme.muted)
    }

    private var selectionMarker: some View {
        Image(systemName: selectionPinned ? "pin.fill" : "scope")
            .foregroundStyle(selectionPinned ? NexusTheme.accent : NexusTheme.muted)
    }

    private func ohlcvMetric(_ label: String, _ value: String, tone: Color = NexusTheme.muted) -> some View {
        HStack(spacing: 3) {
            Text(LocalizedStringKey(label))
                .foregroundStyle(NexusTheme.muted)
            Text(value)
                .foregroundStyle(tone)
        }
        .lineLimit(1)
        .minimumScaleFactor(0.75)
    }

    private func newsRow(_ item: NewsItem) -> some View {
        HStack(alignment: .top, spacing: 6) {
            Circle()
                .fill(NexusTheme.toneColor(item.tone))
                .frame(width: 6, height: 6)
                .padding(.top, 4)
            Text(item.title)
                .font(.caption2)
                .foregroundStyle(NexusTheme.text)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
        }
    }

    private var chartCaption: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 14) {
                captionStats
                Spacer(minLength: 10)
                captionLegend
            }
            if !compactMode, !captionMetaItems.isEmpty {
                captionMetaLine
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var captionStats: some View {
        let rows = windowedPoints
        let change: Double? = {
            guard let last = rows.last, let first = rows.first, first.close != 0 else { return nil }
            return (last.close / first.close - 1) * 100
        }()
        return HStack(alignment: .firstTextBaseline, spacing: 12) {
            captionInline("Máx", rows.map(\.high).max().map(priceText) ?? "—")
            captionInline("Mín", rows.map(\.low).min().map(priceText) ?? "—")
            captionInline("Δ \(range.label)", formatPct(change))
            Text("\(rows.count) velas · \(interval.label)")
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
        }
        .fixedSize(horizontal: true, vertical: false)
    }

    private var captionLegend: some View {
        HStack(spacing: 10) {
            indicatorLegend(chartStyle.label, NexusTheme.text)
            indicatorLegend(chartScale.label, NexusTheme.muted)
            if showMA20 { indicatorLegend("MA20", .white) }
            if showMA50 { indicatorLegend("MA50", NexusTheme.accent) }
            if showMA200 { indicatorLegend("MA200", NexusTheme.warn) }
            if showVolume, windowedPoints.contains(where: { ($0.volume ?? 0) > 0 }) {
                indicatorLegend("Volumen", NexusTheme.muted)
            }
            if compareSPY, !windowedBenchmark.isEmpty {
                indicatorLegend("Activo base 100", NexusTheme.accent)
                indicatorLegend("SPY base 100", NexusTheme.warn)
            }
        }
        .fixedSize(horizontal: true, vertical: false)
    }

    private var captionMetaLine: some View {
        captionMetaText
            .font(.caption2)
            .frame(maxWidth: .infinity, alignment: .leading)
            .fixedSize(horizontal: false, vertical: true)
    }

    private var captionMetaItems: [(text: String, tone: Color)] {
        var items: [(String, Color)] = []
        if windowedPoints.contains(where: \.syntheticOHLC) {
            items.append(("Parte de la serie usa cierre sintético", NexusTheme.warn))
        }
        if let status = series.status, let source = series.source {
            let asOf = series.asOf.map { " · última \($0)" } ?? ""
            items.append(("Datos \(status) · \(source)\(asOf)", NexusTheme.muted))
        }
        if let state = [series.marketState, series.dataStatus]
            .compactMap({ $0 })
            .first(where: { $0.lowercased() != "unknown" }) {
            items.append(("Mercado/datos: \(state)", NexusTheme.muted))
        }
        if let adjustment = series.adjustment {
            items.append(
                ("Ajuste: \(adjustment) · sesión \(series.session ?? "—") · \(series.timezone ?? "UTC")", NexusTheme.muted)
            )
        }
        if showRelative, let rel = visibleRelSpy {
            items.append(("Relativo vs SPY \(formatPct(rel)) en la ventana visible", NexusTheme.muted))
        }
        if showNews, !cachedNewsFlags.isEmpty {
            items.append(("Puntos sobre velas: titulares, no señales", NexusTheme.muted))
        }
        return items
    }

    private var captionMetaText: Text {
        captionMetaItems.enumerated().reduce(Text("")) { acc, pair in
            let piece = Text(pair.element.text).foregroundStyle(pair.element.tone)
            if pair.offset == 0 { return piece }
            return acc + Text("   ·   ").foregroundStyle(NexusTheme.muted.opacity(0.55)) + piece
        }
    }

    private var visibleRelSpy: Double? {
        guard showRelative, (ticker ?? "").uppercased() != "SPY" else { return nil }
        let rows = windowedPoints
        guard let first = rows.first, let last = rows.last, first.close != 0 else { return nil }
        guard let spyFirst = nearest(in: windowedBenchmark, to: first.date)?.close,
              let spyLast = nearest(in: windowedBenchmark, to: last.date)?.close,
              spyFirst != 0 else { return nil }
        return ((last.close / first.close) - (spyLast / spyFirst)) * 100
    }

    private func captionInline(_ title: String, _ value: String) -> some View {
        HStack(spacing: 4) {
            Text(LocalizedStringKey(title))
                .font(.caption2.weight(.bold))
                .foregroundStyle(NexusTheme.muted)
            Text(value)
                .font(.caption.monospacedDigit().weight(.semibold))
        }
    }

    private func indicatorLegend(_ title: String, _ color: Color) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 5, height: 5)
            Text(LocalizedStringKey(title))
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
        }
    }

    private func priceText(_ value: Double) -> String {
        String(format: "%.\(valueDigits)f", value)
    }

    private func volumeText(_ value: Double?) -> String {
        guard let value, value > 0 else { return "—" }
        if value >= 1_000_000_000 { return String(format: "%.1fB", value / 1_000_000_000) }
        if value >= 1_000_000 { return String(format: "%.1fM", value / 1_000_000) }
        if value >= 1_000 { return String(format: "%.1fK", value / 1_000) }
        return String(format: "%.0f", value)
    }

    private func selectionDateText(_ date: Date) -> String {
        if interval == .oneDay || interval == .oneWeek {
            return date.formatted(.dateTime.day().month(.abbreviated).year())
        }
        return date.formatted(.dateTime.day().month(.abbreviated).hour().minute())
    }

    private func nearest(in rows: [CandlePoint], to date: Date, limit: TimeInterval = 8 * 86_400) -> CandlePoint? {
        guard let nearest = rows.min(by: {
            abs($0.date.timeIntervalSince(date)) < abs($1.date.timeIntervalSince(date))
        }) else { return nil }
        return abs(nearest.date.timeIntervalSince(date)) <= limit ? nearest : nil
    }
}

struct CandlePoint: Identifiable {
    let id: Int
    let date: Date
    let close: Double
    let open: Double
    let high: Double
    let low: Double
    let volume: Double?
    let ma20: Double?
    let ma50: Double?
    let ma200: Double?
    let rsi14: Double?
    let macd: Double?
    let macdSignal: Double?
    let syntheticOHLC: Bool
    var bullish: Bool { close >= open }

    static func parse(_ points: [SparklinePoint]) -> [CandlePoint] {
        var previous: Double?
        var ema12: Double?
        var ema26: Double?
        var signalEMA: Double?
        var changes: [Double] = []
        var rows: [CandlePoint] = []
        rows.reserveCapacity(points.count)
        for (index, point) in points.enumerated() {
            guard let date = point.epochUTC.map(Date.init(timeIntervalSince1970:))
                    ?? parseFlexibleDate(point.date),
                  let close = point.value else { continue }
            let hasRealOHLC = point.open != nil && point.high != nil && point.low != nil
            let synthetic = point.syntheticOHLC ?? !hasRealOHLC
            let open = point.open ?? previous ?? close
            if let previous {
                changes.append(close - previous)
            }
            ema12 = ema(previous: ema12, value: close, period: 12)
            ema26 = ema(previous: ema26, value: close, period: 26)
            let macd = index >= 25
                ? zipOptional(ema12, ema26).map { $0.0 - $0.1 }
                : nil
            if let macd {
                signalEMA = ema(previous: signalEMA, value: macd, period: 9)
            }
            let rsi: Double? = changes.count >= 14 ? rsi14(Array(changes.suffix(14))) : nil
            rows.append(CandlePoint(
                id: index,
                date: date,
                close: close,
                open: open,
                high: point.high ?? max(open, close),
                low: point.low ?? min(open, close),
                volume: point.volume,
                ma20: point.ma20,
                ma50: point.ma50,
                ma200: point.ma200,
                rsi14: rsi,
                macd: macd,
                macdSignal: index >= 33 ? signalEMA : nil,
                syntheticOHLC: synthetic
            ))
            previous = close
        }
        return rows
    }

    private static func ema(previous: Double?, value: Double, period: Double) -> Double {
        guard let previous else { return value }
        let alpha = 2 / (period + 1)
        return value * alpha + previous * (1 - alpha)
    }

    private static func zipOptional(_ lhs: Double?, _ rhs: Double?) -> (Double, Double)? {
        guard let lhs, let rhs else { return nil }
        return (lhs, rhs)
    }

    private static func rsi14(_ changes: [Double]) -> Double {
        let gains = changes.reduce(0) { $0 + max($1, 0) } / Double(changes.count)
        let losses = changes.reduce(0) { $0 + max(-$1, 0) } / Double(changes.count)
        guard losses > 0 else { return 100 }
        return 100 - 100 / (1 + gains / losses)
    }

    static func pixelLOD(_ rows: [CandlePoint], maxBars: Int) -> [CandlePoint] {
        guard maxBars >= 2, rows.count > maxBars else { return rows }
        let bucketSize = Int(ceil(Double(rows.count) / Double(maxBars)))
        return stride(from: 0, to: rows.count, by: bucketSize).compactMap { start in
            let end = min(start + bucketSize, rows.count)
            let bucket = rows[start..<end]
            guard let first = bucket.first, let last = bucket.last else { return nil }
            return CandlePoint(
                id: first.id,
                date: last.date,
                close: last.close,
                open: first.open,
                high: bucket.map(\.high).max() ?? last.high,
                low: bucket.map(\.low).min() ?? last.low,
                volume: bucket.compactMap(\.volume).reduce(0, +),
                ma20: last.ma20,
                ma50: last.ma50,
                ma200: last.ma200,
                rsi14: last.rsi14,
                macd: last.macd,
                macdSignal: last.macdSignal,
                syntheticOHLC: bucket.contains(where: \.syntheticOHLC)
            )
        }
    }
}

struct CandleNewsFlag {
    let date: Date
    let y: Double
    let tone: String?
    let items: [NewsItem]
}

struct NexusCandlePlot: View {
    let rows: [CandlePoint]
    let benchmark: [CandlePoint]
    let selectedDate: Date?
    let news: [CandleNewsFlag]
    let valueDigits: Int
    let interval: NexusChartInterval
    let style: NexusChartStyle
    let scale: NexusChartScale
    let compareNormalized: Bool
    var minHeight: CGFloat = 180
    let showVolume: Bool
    let showMA20: Bool
    let showMA50: Bool
    let showMA200: Bool
    let resetID: Int
    let goLatestID: Int
    let onSelect: (Date) -> Void
    let onPinChange: (Bool) -> Void
    let onClearSelection: () -> Void

    @State private var zoomScale: CGFloat = 1
    @State private var endOffset = 0

    var body: some View {
        GeometryReader { geo in
            let visibleRows = viewportRows
            let visibleBenchmark = benchmark.filter {
                guard let first = visibleRows.first?.date, let last = visibleRows.last?.date else { return false }
                return $0.date >= first && $0.date <= last
            }
            let renderVolume = showVolume && visibleRows.contains { ($0.volume ?? 0) > 0 }
            let interactionLayout = CandleLayout(
                size: geo.size,
                rows: visibleRows,
                showVolume: renderVolume,
                scale: scale
            )
            let maxBars = max(66, Int(interactionLayout.plot.width / 1.5))
            let renderRows = CandlePoint.pixelLOD(visibleRows, maxBars: maxBars)
            let renderBenchmark = CandlePoint.pixelLOD(visibleBenchmark, maxBars: maxBars)
            let renderLayout = CandleLayout(
                size: geo.size,
                rows: renderRows,
                showVolume: renderVolume,
                scale: scale
            )
            ZStack {
                Canvas { context, _ in
                    drawStatic(
                        context: context,
                        layout: renderLayout,
                        benchmark: renderBenchmark
                    )
                }
                .allowsHitTesting(false)
                Canvas { context, _ in
                    drawSelection(
                        context: context,
                        layout: interactionLayout,
                        horizontal: !compareNormalized
                    )
                }
                .allowsHitTesting(false)
                ChartInteractionOverlay(
                    onSelect: { location in
                        guard let index = interactionLayout.index(at: location),
                              visibleRows.indices.contains(index) else { return }
                        onSelect(visibleRows[index].date)
                    },
                    onPinChange: onPinChange,
                    onPan: { delta in
                        pan(by: delta, step: interactionLayout.step)
                    },
                    onZoom: { magnification, location in
                        zoom(
                            by: magnification,
                            anchorX: location.x,
                            plot: interactionLayout.plot
                        )
                    },
                    onReset: resetViewport,
                    onClear: onClearSelection,
                    onStepSelection: { step in
                        guard !visibleRows.isEmpty else { return }
                        let current = selectedDate.flatMap { selected in
                            visibleRows.firstIndex(where: { $0.date == selected })
                        } ?? (visibleRows.count - 1)
                        let next = max(0, min(visibleRows.count - 1, current + step))
                        onSelect(visibleRows[next].date)
                        onPinChange(true)
                    }
                )
            }
        }
        .frame(maxWidth: .infinity)
        .frame(minHeight: minHeight)
        .onChange(of: resetID) { _, _ in resetViewport() }
        .onChange(of: goLatestID) { _, _ in endOffset = 0 }
        .onChange(of: rows.count) { _, _ in resetViewport() }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Gráfico \(style.label.lowercased()), intervalo \(interval.label)")
        .accessibilityValue(accessibilitySummary)
        .accessibilityHint("Usa flecha izquierda y derecha para recorrer datos; Escape libera la selección.")
        .accessibilityAdjustableAction { direction in
            let current = selectedDate.flatMap { date in rows.firstIndex(where: { $0.date == date }) }
            let index: Int
            switch direction {
            case .increment:
                index = min((current ?? -1) + 1, rows.count - 1)
            case .decrement:
                index = max((current ?? rows.count) - 1, 0)
            @unknown default:
                return
            }
            guard rows.indices.contains(index) else { return }
            onSelect(rows[index].date)
        }
    }

    private var viewportRows: [CandlePoint] {
        guard rows.count > 2 else { return rows }
        let count = min(rows.count, max(2, Int(CGFloat(rows.count) / zoomScale)))
        let end = max(count, min(rows.count, rows.count - endOffset))
        guard count <= end, end <= rows.count else { return rows }
        return Array(rows[(end - count)..<end])
    }

    private func pan(by delta: CGFloat, step: CGFloat) {
        guard zoomScale > 1.001, abs(delta) > 0.1 else { return }
        let bars = Int((delta / max(step, 0.5)).rounded())
        guard bars != 0 else { return }
        let visibleCount = viewportRows.count
        endOffset = max(0, min(rows.count - visibleCount, endOffset + bars))
    }

    private func zoom(by magnification: CGFloat, anchorX: CGFloat, plot: CGRect) {
        let oldCount = viewportRows.count
        let oldEnd = max(oldCount, min(rows.count, rows.count - endOffset))
        let oldStart = oldEnd - oldCount
        let fraction = max(0, min(1, (anchorX - plot.minX) / max(plot.width, 1)))
        let anchorIndex = oldStart + Int(fraction * CGFloat(max(oldCount - 1, 1)))
        let factor = max(0.5, min(1.5, 1 + magnification))
        zoomScale = max(1, min(20, zoomScale * factor))
        let newCount = min(rows.count, max(2, Int(CGFloat(rows.count) / zoomScale)))
        let newStart = max(0, min(rows.count - newCount, anchorIndex - Int(fraction * CGFloat(newCount))))
        let newEnd = newStart + newCount
        endOffset = max(0, rows.count - newEnd)
    }

    private func resetViewport() {
        zoomScale = 1
        endOffset = 0
    }

    private var accessibilitySummary: String {
        guard let first = rows.first, let last = rows.last else { return "Sin datos" }
        if let selectedDate,
           let row = rows.first(where: { $0.date == selectedDate }) {
            return "\(row.date.formatted(date: .abbreviated, time: .omitted)), apertura \(priceLabel(row.open)), máximo \(priceLabel(row.high)), mínimo \(priceLabel(row.low)), cierre \(priceLabel(row.close))"
        }
        let change = first.close == 0 ? 0 : (last.close / first.close - 1) * 100
        return "\(rows.count) sesiones, variación \(String(format: "%.1f", change)) por ciento"
    }

    private func drawStatic(
        context: GraphicsContext,
        layout renderLayout: CandleLayout,
        benchmark: [CandlePoint]
    ) {
        guard rows.count >= 2 else { return }
        if compareNormalized, benchmark.count >= 2 {
            drawNormalizedComparison(
                context: context,
                layout: renderLayout,
                benchmark: benchmark
            )
        } else {
            drawGrid(context: context, layout: renderLayout)
            switch style {
            case .candles:
                drawCandles(context: context, layout: renderLayout)
            case .line:
                drawPriceLine(context: context, layout: renderLayout, fill: false)
            case .area:
                drawPriceLine(context: context, layout: renderLayout, fill: true)
            }
        }
        if renderLayout.volumePlot.height > 0 {
            drawVolume(context: context, layout: renderLayout)
        }
        if showMA20, !compareNormalized {
            drawMA(context: context, layout: renderLayout, keyPath: \.ma20, color: .white)
        }
        if showMA50, !compareNormalized {
            drawMA(context: context, layout: renderLayout, keyPath: \.ma50, color: NexusTheme.accent)
        }
        if showMA200, !compareNormalized {
            drawMA(context: context, layout: renderLayout, keyPath: \.ma200, color: NexusTheme.warn)
        }
        if !compareNormalized {
            drawNews(context: context, layout: renderLayout)
        }
        drawLast(context: context, layout: renderLayout)
        drawAxes(context: context, layout: renderLayout, showPrices: !compareNormalized)
    }

    private func drawGrid(context: GraphicsContext, layout: CandleLayout) {
        var grid = Path()
        for y in layout.priceTicks.map(\.y) {
            grid.move(to: CGPoint(x: layout.plot.minX, y: y))
            grid.addLine(to: CGPoint(x: layout.plot.maxX, y: y))
        }
        context.stroke(grid, with: .color(NexusTheme.border.opacity(0.55)), lineWidth: 0.5)
    }

    private func drawCandles(context: GraphicsContext, layout: CandleLayout) {
        let bodyWidth = max(1.2, layout.step * 0.62)
        var bullishWicks = Path()
        var bearishWicks = Path()
        var bullishBodies = Path()
        var bearishBodies = Path()
        var syntheticCloses = Path()
        for (index, row) in layout.rows.enumerated() {
            let x = layout.x(for: index)
            if row.syntheticOHLC {
                let y = layout.y(row.close)
                syntheticCloses.move(to: CGPoint(x: x - bodyWidth / 2, y: y))
                syntheticCloses.addLine(to: CGPoint(x: x + bodyWidth / 2, y: y))
                continue
            }
            var wick = Path()
            wick.move(to: CGPoint(x: x, y: layout.y(row.high)))
            wick.addLine(to: CGPoint(x: x, y: layout.y(row.low)))
            let top = layout.y(max(row.open, row.close))
            let bottom = layout.y(min(row.open, row.close))
            let height = max(1, bottom - top)
            let body = CGRect(x: x - bodyWidth / 2, y: top, width: bodyWidth, height: height)
            if row.bullish {
                bullishWicks.addPath(wick)
                bullishBodies.addRect(body)
            } else {
                bearishWicks.addPath(wick)
                bearishBodies.addRect(body)
            }
        }
        context.stroke(bullishWicks, with: .color(NexusTheme.good), lineWidth: 1)
        context.stroke(bearishWicks, with: .color(NexusTheme.bad), lineWidth: 1)
        context.fill(bullishBodies, with: .color(NexusTheme.good))
        context.fill(bearishBodies, with: .color(NexusTheme.bad))
        context.stroke(
            syntheticCloses,
            with: .color(NexusTheme.warn),
            style: StrokeStyle(lineWidth: 1.2, dash: [2, 2])
        )
    }

    private func drawPriceLine(context: GraphicsContext, layout: CandleLayout, fill: Bool) {
        guard let first = layout.rows.first else { return }
        var line = Path()
        line.move(to: CGPoint(x: layout.x(for: 0), y: layout.y(first.close)))
        for (index, row) in layout.rows.dropFirst().enumerated() {
            line.addLine(to: CGPoint(x: layout.x(for: index + 1), y: layout.y(row.close)))
        }
        if fill {
            var area = line
            area.addLine(to: CGPoint(x: layout.x(for: layout.rows.count - 1), y: layout.plot.maxY))
            area.addLine(to: CGPoint(x: layout.x(for: 0), y: layout.plot.maxY))
            area.closeSubpath()
            context.fill(area, with: .color(NexusTheme.accent.opacity(0.16)))
        }
        context.stroke(line, with: .color(NexusTheme.accent), lineWidth: 1.5)
    }

    private func drawNormalizedComparison(
        context: GraphicsContext,
        layout: CandleLayout,
        benchmark: [CandlePoint]
    ) {
        guard let assetBase = layout.rows.first?.close,
              let benchmarkBase = benchmark.first?.close,
              assetBase != 0,
              benchmarkBase != 0 else { return }
        let assetValues = layout.rows.map { $0.close / assetBase * 100 }
        let benchmarkValues = benchmark.map { $0.close / benchmarkBase * 100 }
        let all = assetValues + benchmarkValues
        guard let rawLo = all.min(), let rawHi = all.max() else { return }
        let pad = max((rawHi - rawLo) * 0.08, 0.5)
        let lo = rawLo - pad
        let hi = rawHi + pad
        func y(_ value: Double) -> CGFloat {
            layout.plot.maxY - CGFloat((value - lo) / max(hi - lo, 0.0001)) * layout.plot.height
        }
        var grid = Path()
        for step in 0..<4 {
            let value = hi - (hi - lo) * Double(step) / 3
            let yValue = y(value)
            grid.move(to: CGPoint(x: layout.plot.minX, y: yValue))
            grid.addLine(to: CGPoint(x: layout.plot.maxX, y: yValue))
            context.draw(
                Text(String(format: "%.1f", value))
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(NexusTheme.muted),
                at: CGPoint(x: 2, y: yValue),
                anchor: .leading
            )
        }
        context.stroke(grid, with: .color(NexusTheme.border.opacity(0.55)), lineWidth: 0.5)

        var assetPath = Path()
        for (index, value) in assetValues.enumerated() {
            let point = CGPoint(x: layout.x(for: index), y: y(value))
            if index == 0 { assetPath.move(to: point) } else { assetPath.addLine(to: point) }
        }
        context.stroke(assetPath, with: .color(NexusTheme.accent), lineWidth: 1.6)

        var benchmarkPath = Path()
        let benchmarkStep = layout.plot.width / CGFloat(max(benchmarkValues.count, 1))
        for (index, value) in benchmarkValues.enumerated() {
            let x = layout.plot.minX + (CGFloat(index) + 0.5) * benchmarkStep
            let point = CGPoint(x: x, y: y(value))
            if index == 0 { benchmarkPath.move(to: point) } else { benchmarkPath.addLine(to: point) }
        }
        context.stroke(
            benchmarkPath,
            with: .color(NexusTheme.warn),
            style: StrokeStyle(lineWidth: 1.4, dash: [5, 3])
        )
    }

    private func drawVolume(context: GraphicsContext, layout: CandleLayout) {
        guard layout.maxVolume > 0, layout.volumePlot.height > 0 else { return }
        let bodyWidth = max(1, layout.step * 0.7)
        var bullish = Path()
        var bearish = Path()
        for (index, row) in layout.rows.enumerated() {
            guard let volume = row.volume, volume > 0 else { continue }
            let height = CGFloat(volume / layout.maxVolume) * layout.volumePlot.height
            let rect = CGRect(
                x: layout.x(for: index) - bodyWidth / 2,
                y: layout.volumePlot.maxY - height,
                width: bodyWidth,
                height: max(1, height)
            )
            if row.bullish { bullish.addRect(rect) } else { bearish.addRect(rect) }
        }
        context.fill(bullish, with: .color(NexusTheme.good.opacity(0.35)))
        context.fill(bearish, with: .color(NexusTheme.bad.opacity(0.35)))
    }

    private func drawMA(
        context: GraphicsContext,
        layout: CandleLayout,
        keyPath: KeyPath<CandlePoint, Double?>,
        color: Color
    ) {
        var path = Path()
        var started = false
        for (index, row) in layout.rows.enumerated() {
            guard let ma = row[keyPath: keyPath] else {
                started = false
                continue
            }
            let point = CGPoint(x: layout.x(for: index), y: layout.y(ma))
            if started {
                path.addLine(to: point)
            } else {
                path.move(to: point)
                started = true
            }
        }
        guard started else { return }
        context.stroke(
            path,
            with: .color(color.opacity(0.78)),
            style: StrokeStyle(lineWidth: 1.1, dash: [4, 3])
        )
    }

    private func drawNews(context: GraphicsContext, layout: CandleLayout) {
        for flag in news {
            guard let index = layout.rows.enumerated().min(by: {
                abs($0.element.date.timeIntervalSince(flag.date)) <
                    abs($1.element.date.timeIntervalSince(flag.date))
            })?.offset else { continue }
            let point = CGPoint(x: layout.x(for: index), y: layout.y(flag.y) - 6)
            let diameter: CGFloat = flag.items.count > 1 ? 12 : 7
            let dot = Path(ellipseIn: CGRect(
                x: point.x - diameter / 2,
                y: point.y - diameter / 2,
                width: diameter,
                height: diameter
            ))
            context.fill(dot, with: .color(NexusTheme.toneColor(flag.tone)))
            if flag.items.count > 1 {
                context.draw(
                    Text("\(flag.items.count)")
                        .font(.system(size: 7, weight: .bold))
                        .foregroundColor(.white),
                    at: point,
                    anchor: .center
                )
            }
        }
    }

    private func drawSelection(
        context: GraphicsContext,
        layout: CandleLayout,
        horizontal: Bool
    ) {
        guard let selectedDate else { return }
        guard let index = layout.rows.firstIndex(where: { $0.date == selectedDate }) else { return }
        let x = layout.x(for: index)
        let y = layout.y(layout.rows[index].close)
        var line = Path()
        line.move(to: CGPoint(x: x, y: layout.plot.minY))
        line.addLine(to: CGPoint(x: x, y: layout.interactionPlot.maxY))
        if horizontal {
            line.move(to: CGPoint(x: layout.plot.minX, y: y))
            line.addLine(to: CGPoint(x: layout.plot.maxX, y: y))
        }
        context.stroke(
            line,
            with: .color(NexusTheme.text.opacity(0.4)),
            style: StrokeStyle(lineWidth: 1, dash: [3, 3])
        )
        let dot = Path(ellipseIn: CGRect(x: x - 3, y: y - 3, width: 6, height: 6))
        context.fill(dot, with: .color(NexusTheme.text))
        if horizontal {
            context.draw(
                Text(priceLabel(layout.rows[index].close))
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(NexusTheme.text),
                at: CGPoint(x: 2, y: y),
                anchor: .leading
            )
        }
    }

    private func drawLast(context: GraphicsContext, layout: CandleLayout) {
        guard let last = layout.rows.last else { return }
        let point = CGPoint(x: layout.x(for: layout.rows.count - 1), y: layout.y(last.close))
        let dot = Path(ellipseIn: CGRect(x: point.x - 2.5, y: point.y - 2.5, width: 5, height: 5))
        context.fill(dot, with: .color(NexusTheme.text))
    }

    private func drawAxes(
        context: GraphicsContext,
        layout: CandleLayout,
        showPrices: Bool
    ) {
        if showPrices {
            for tick in layout.priceTicks {
                let text = Text(priceLabel(tick.price))
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(NexusTheme.muted)
                context.draw(text, at: CGPoint(x: 2, y: tick.y), anchor: .leading)
            }
        }
        let dateCount = min(5, layout.rows.count)
        guard dateCount > 1 else { return }
        for step in 0..<dateCount {
            let index = Int(round(Double(step) / Double(dateCount - 1) * Double(layout.rows.count - 1)))
            let row = layout.rows[index]
            let format: Date.FormatStyle = interval == .oneDay || interval == .oneWeek
                ? .dateTime.day().month(.abbreviated)
                : .dateTime.day().hour().minute()
            let label = Text(row.date, format: format)
                .font(.system(size: 9))
                .foregroundColor(NexusTheme.muted)
            context.draw(label, at: CGPoint(x: layout.x(for: index), y: layout.size.height - 7), anchor: .center)
        }
    }

    private func priceLabel(_ value: Double) -> String {
        String(format: "%.\(valueDigits)f", value)
    }
}

private enum NexusIndicatorKind {
    case rsi
    case macd
}

private struct NexusIndicatorPlot: View {
    let rows: [CandlePoint]
    let kind: NexusIndicatorKind
    let selectedDate: Date?

    var body: some View {
        Canvas { context, size in
            let plot = CGRect(x: 34, y: 7, width: max(1, size.width - 40), height: max(1, size.height - 14))
            switch kind {
            case .rsi:
                drawRSI(context: context, plot: plot)
            case .macd:
                drawMACD(context: context, plot: plot)
            }
            drawSelection(context: context, plot: plot)
        }
        .frame(height: kind == .rsi ? 112 : 92)
        .background(NexusTheme.cardInner.opacity(0.65))
        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(kind == .rsi ? "RSI de 14 periodos" : "MACD 12, 26, 9")
        .accessibilityValue(accessibilityValue)
    }

    private func drawRSI(context: GraphicsContext, plot: CGRect) {
        func y(_ value: Double) -> CGFloat {
            plot.maxY - CGFloat(value / 100) * plot.height
        }
        func x(_ index: Int) -> CGFloat {
            plot.minX + (CGFloat(index) + 0.5) / CGFloat(max(rows.count, 1)) * plot.width
        }

        context.fill(
            Path(CGRect(x: plot.minX, y: plot.minY, width: plot.width, height: max(0, y(70) - plot.minY))),
            with: .color(NexusTheme.bad.opacity(0.055))
        )
        context.fill(
            Path(CGRect(x: plot.minX, y: y(30), width: plot.width, height: max(0, plot.maxY - y(30)))),
            with: .color(NexusTheme.good.opacity(0.055))
        )

        let levels: [(Double, Color)] = [
            (70, Color.purple),
            (60, NexusTheme.bad),
            (30, NexusTheme.good),
            (20, Color.cyan),
        ]
        for (value, color) in levels {
            context.draw(
                Text(String(format: "%.0f", value))
                    .font(.system(size: 8, design: .monospaced))
                    .foregroundColor(NexusTheme.muted),
                at: CGPoint(x: 3, y: y(value)),
                anchor: .leading
            )
            var level = Path()
            level.move(to: CGPoint(x: plot.minX, y: y(value)))
            level.addLine(to: CGPoint(x: plot.maxX, y: y(value)))
            context.stroke(
                level,
                with: .color(color.opacity(0.72)),
                style: StrokeStyle(lineWidth: 0.65, dash: [2, 3])
            )
        }
        var line = Path()
        var started = false
        for (index, row) in rows.enumerated() {
            guard let value = row.rsi14 else { continue }
            let point = CGPoint(x: x(index), y: y(value))
            if started { line.addLine(to: point) } else { line.move(to: point); started = true }
        }
        context.stroke(line, with: .color(.white.opacity(0.92)), lineWidth: 1.3)

        for divergence in rsiDivergences() {
            guard let fromRSI = rows[divergence.from].rsi14,
                  let toRSI = rows[divergence.to].rsi14 else { continue }
            let tone = divergence.bullish ? NexusTheme.good : NexusTheme.bad
            let start = CGPoint(x: x(divergence.from), y: y(fromRSI))
            let end = CGPoint(x: x(divergence.to), y: y(toRSI))
            var path = Path()
            path.move(to: start)
            path.addLine(to: end)
            context.stroke(path, with: .color(tone), lineWidth: 1.7)
            context.fill(Path(ellipseIn: CGRect(x: end.x - 2.5, y: end.y - 2.5, width: 5, height: 5)), with: .color(tone))
            context.draw(
                Text(divergence.bullish ? "ALC" : "BAJ")
                    .font(.system(size: 7, weight: .bold))
                    .foregroundColor(tone),
                at: CGPoint(x: end.x, y: end.y + (divergence.bullish ? -8 : 8)),
                anchor: .center
            )
        }
    }

    private struct RSIDivergence {
        let from: Int
        let to: Int
        let bullish: Bool
    }

    private func rsiDivergences() -> [RSIDivergence] {
        let leftBars = 15
        let rightBars = 2
        let pivotLookback = 5
        guard rows.count > leftBars + rightBars else { return [] }

        var highs: [Int] = []
        var lows: [Int] = []
        var result: [RSIDivergence] = []

        for index in leftBars..<(rows.count - rightBars) {
            guard let rsi = rows[index].rsi14 else { continue }
            let close = rows[index].close

            if isPivot(index: index, left: leftBars, right: rightBars, high: true) {
                if let previous = highs.suffix(pivotLookback).reversed().first(where: { prior in
                    guard let priorRSI = rows[prior].rsi14 else { return false }
                    return close > rows[prior].close
                        && rsi < priorRSI
                        && max(rsi, priorRSI) >= 70
                }) {
                    result.append(RSIDivergence(from: previous, to: index, bullish: false))
                }
                highs.append(index)
            }

            if isPivot(index: index, left: leftBars, right: rightBars, high: false) {
                if let previous = lows.suffix(pivotLookback).reversed().first(where: { prior in
                    guard let priorRSI = rows[prior].rsi14 else { return false }
                    return close < rows[prior].close
                        && rsi > priorRSI
                        && min(rsi, priorRSI) <= 30
                }) {
                    result.append(RSIDivergence(from: previous, to: index, bullish: true))
                }
                lows.append(index)
            }
        }
        return Array(result.suffix(8))
    }

    private func isPivot(index: Int, left: Int, right: Int, high: Bool) -> Bool {
        let value = rows[index].close
        let lower = index - left
        let upper = index + right
        for candidate in lower...upper where candidate != index {
            if high, rows[candidate].close >= value { return false }
            if !high, rows[candidate].close <= value { return false }
        }
        return true
    }

    private func drawMACD(context: GraphicsContext, plot: CGRect) {
        let values = rows.flatMap { [$0.macd, $0.macdSignal].compactMap { $0 } }
        let span = max(values.map(abs).max() ?? 0, 0.000_001)
        func y(_ value: Double) -> CGFloat {
            plot.midY - CGFloat(value / span) * plot.height * 0.46
        }
        var zero = Path()
        zero.move(to: CGPoint(x: plot.minX, y: plot.midY))
        zero.addLine(to: CGPoint(x: plot.maxX, y: plot.midY))
        context.stroke(zero, with: .color(NexusTheme.border), lineWidth: 0.5)
        context.draw(
            Text("MACD")
                .font(.system(size: 8, weight: .semibold))
                .foregroundColor(NexusTheme.muted),
            at: CGPoint(x: 3, y: 8),
            anchor: .topLeading
        )

        let step = plot.width / CGFloat(max(rows.count, 1))
        var macdPath = Path()
        var signalPath = Path()
        var macdStarted = false
        var signalStarted = false
        for (index, row) in rows.enumerated() {
            let x = plot.minX + (CGFloat(index) + 0.5) * step
            if let macd = row.macd {
                let point = CGPoint(x: x, y: y(macd))
                if macdStarted { macdPath.addLine(to: point) } else { macdPath.move(to: point); macdStarted = true }
                if let signal = row.macdSignal {
                    let histogram = macd - signal
                    let top = y(max(histogram, 0))
                    let bottom = y(min(histogram, 0))
                    let bar = CGRect(x: x - max(0.5, step * 0.3), y: top, width: max(1, step * 0.6), height: max(1, bottom - top))
                    context.fill(Path(bar), with: .color(histogram >= 0 ? NexusTheme.good.opacity(0.35) : NexusTheme.bad.opacity(0.35)))
                }
            }
            if let signal = row.macdSignal {
                let point = CGPoint(x: x, y: y(signal))
                if signalStarted { signalPath.addLine(to: point) } else { signalPath.move(to: point); signalStarted = true }
            }
        }
        context.stroke(macdPath, with: .color(NexusTheme.accent), lineWidth: 1.15)
        context.stroke(signalPath, with: .color(NexusTheme.warn), lineWidth: 1)
    }

    private func drawSelection(context: GraphicsContext, plot: CGRect) {
        guard let selectedDate,
              let index = rows.enumerated().min(by: {
                  abs($0.element.date.timeIntervalSince(selectedDate))
                      < abs($1.element.date.timeIntervalSince(selectedDate))
              })?.offset else { return }
        let x = plot.minX + (CGFloat(index) + 0.5) / CGFloat(max(rows.count, 1)) * plot.width
        var line = Path()
        line.move(to: CGPoint(x: x, y: plot.minY))
        line.addLine(to: CGPoint(x: x, y: plot.maxY))
        context.stroke(
            line,
            with: .color(NexusTheme.text.opacity(0.4)),
            style: StrokeStyle(lineWidth: 1, dash: [3, 3])
        )
    }

    private var accessibilityValue: String {
        guard let last = rows.last else { return "Sin datos" }
        switch kind {
        case .rsi:
            return last.rsi14.map { String(format: "%.1f", $0) } ?? "Sin datos suficientes"
        case .macd:
            guard let macd = last.macd else { return "Sin datos suficientes" }
            return "MACD \(String(format: "%.3f", macd)), señal \(last.macdSignal.map { String(format: "%.3f", $0) } ?? "no disponible")"
        }
    }
}

private struct CandleLayout {
    let size: CGSize
    let rows: [CandlePoint]
    let scale: NexusChartScale
    let plot: CGRect
    let volumePlot: CGRect
    let interactionPlot: CGRect
    let maxVolume: Double
    let lo: Double
    let hi: Double
    let step: CGFloat

    init(
        size: CGSize,
        rows: [CandlePoint],
        showVolume: Bool = false,
        scale: NexusChartScale = .linear
    ) {
        self.size = size
        self.rows = rows
        self.scale = scale
        let left: CGFloat = 52
        let bottom: CGFloat = 20
        let top: CGFloat = 8
        let right: CGFloat = 8
        let availableHeight = max(1, size.height - top - bottom)
        let volumeHeight = showVolume ? max(26, availableHeight * 0.2) : 0
        let volumeGap: CGFloat = showVolume ? 6 : 0
        plot = CGRect(
            x: left,
            y: top,
            width: max(1, size.width - left - right),
            height: max(1, availableHeight - volumeHeight - volumeGap)
        )
        volumePlot = CGRect(
            x: plot.minX,
            y: plot.maxY + volumeGap,
            width: plot.width,
            height: volumeHeight
        )
        interactionPlot = CGRect(
            x: plot.minX,
            y: plot.minY,
            width: plot.width,
            height: max(plot.height, volumePlot.maxY - plot.minY)
        )
        let movingAverages = rows.compactMap(\.ma20) + rows.compactMap(\.ma50) + rows.compactMap(\.ma200)
        let lows = (rows.map(\.low) + movingAverages).map { Self.transform($0, scale: scale) }
        let highs = (rows.map(\.high) + movingAverages).map { Self.transform($0, scale: scale) }
        let rawLo = lows.min() ?? 0
        let rawHi = highs.max() ?? 1
        let pad = max((rawHi - rawLo) * 0.08, abs(rawHi) * 0.001)
        lo = rawLo - pad
        hi = rawHi + pad
        step = plot.width / CGFloat(max(rows.count, 1))
        maxVolume = rows.compactMap(\.volume).max() ?? 0
    }

    func x(for index: Int) -> CGFloat {
        plot.minX + (CGFloat(index) + 0.5) * step
    }

    func y(_ price: Double) -> CGFloat {
        let span = max(hi - lo, 0.0001)
        let transformed = Self.transform(price, scale: scale)
        return plot.maxY - CGFloat((transformed - lo) / span) * plot.height
    }

    var priceTicks: [(price: Double, y: CGFloat)] {
        (0..<4).map { step in
            let t = Double(step) / 3
            let transformed = hi - (hi - lo) * t
            let price = Self.inverse(transformed, scale: scale)
            return (price, y(price))
        }
    }

    func index(at point: CGPoint) -> Int? {
        guard interactionPlot.insetBy(dx: -6, dy: -4).contains(point) else { return nil }
        let raw = Int(floor((point.x - plot.minX) / step))
        guard rows.indices.contains(raw) else { return nil }
        return raw
    }

    private static func transform(_ value: Double, scale: NexusChartScale) -> Double {
        scale == .logarithmic ? log(max(value, 0.000_000_1)) : value
    }

    private static func inverse(_ value: Double, scale: NexusChartScale) -> Double {
        scale == .logarithmic ? exp(value) : value
    }
}

private struct ChartInteractionOverlay: NSViewRepresentable {
    let onSelect: (CGPoint) -> Void
    let onPinChange: (Bool) -> Void
    let onPan: (CGFloat) -> Void
    let onZoom: (CGFloat, CGPoint) -> Void
    let onReset: () -> Void
    let onClear: () -> Void
    let onStepSelection: (Int) -> Void

    func makeNSView(context: Context) -> ChartInteractionNSView {
        ChartInteractionNSView()
    }

    func updateNSView(_ view: ChartInteractionNSView, context: Context) {
        view.onSelect = onSelect
        view.onPinChange = onPinChange
        view.onPan = onPan
        view.onZoom = onZoom
        view.onReset = onReset
        view.onClear = onClear
        view.onStepSelection = onStepSelection
    }
}

private final class ChartInteractionNSView: NSView {
    var onSelect: ((CGPoint) -> Void)?
    var onPinChange: ((Bool) -> Void)?
    var onPan: ((CGFloat) -> Void)?
    var onZoom: ((CGFloat, CGPoint) -> Void)?
    var onReset: (() -> Void)?
    var onClear: (() -> Void)?
    var onStepSelection: ((Int) -> Void)?

    override var acceptsFirstResponder: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(self)
        if event.clickCount == 2 {
            onReset?()
            return
        }
        onClear?()
        onPinChange?(false)
    }

    override func mouseDragged(with event: NSEvent) {
        onSelect?(swiftUILocation(event))
    }

    override func mouseUp(with event: NSEvent) {
        onClear?()
        onPinChange?(false)
    }

    override func scrollWheel(with event: NSEvent) {
        if abs(event.scrollingDeltaX) > abs(event.scrollingDeltaY) {
            onPan?(event.scrollingDeltaX)
        } else {
            nextResponder?.scrollWheel(with: event)
        }
    }

    override func magnify(with event: NSEvent) {
        onZoom?(event.magnification, swiftUILocation(event))
    }

    override func keyDown(with event: NSEvent) {
        if event.keyCode == 53 {
            onClear?()
        } else if event.keyCode == 123 {
            onStepSelection?(-1)
        } else if event.keyCode == 124 {
            onStepSelection?(1)
        } else {
            super.keyDown(with: event)
        }
    }

    private func swiftUILocation(_ event: NSEvent) -> CGPoint {
        let point = convert(event.locationInWindow, from: nil)
        return CGPoint(x: point.x, y: bounds.height - point.y)
    }
}

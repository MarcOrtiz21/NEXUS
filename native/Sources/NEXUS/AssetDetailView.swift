import SwiftUI

struct AssetDetailView: View {
    @EnvironmentObject private var store: NexusStore
    let ticker: String
    @State private var inspectorTab = "resumen"

    private var score: AssetScore? {
        store.snapshot?.decision?.assetScores?[ticker]
    }

    private var metrics: AssetMetrics? {
        if ticker == "EURUSD" { return store.snapshot?.forex?.EURUSD }
        if ticker == "USDEUR", let eur = store.snapshot?.forex?.EURUSD {
            return AssetMetrics(
                price: inverse(eur.price),
                ma20: inverse(eur.ma20),
                ma50: inverse(eur.ma50),
                ma200: inverse(eur.ma200),
                momentum1m: inverseReturn(eur.momentum1m),
                momentum3m: inverseReturn(eur.momentum3m),
                volatility20d: eur.volatility20d
            )
        }
        if let asset = store.snapshot?.assets?[ticker] { return asset }
        if let company {
            return AssetMetrics(
                price: company.price,
                ma20: nil,
                ma50: nil,
                ma200: nil,
                momentum1m: company.momentum1m,
                momentum3m: company.momentum3m,
                volatility20d: company.volatility20d
            )
        }
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

    /// Tema ETF si el ticker es un proxy de rotación.
    private var rotationTheme: RotationTheme? {
        store.snapshot?.rotation?.themes?.first { $0.ticker == ticker }
    }

    /// Empresa individual si el ticker pertenece a algún cesto temático.
    private var companyMatch: (theme: RotationTheme, company: RotationCompany)? {
        guard let themes = store.snapshot?.rotation?.themes else { return nil }
        for theme in themes {
            if let company = theme.companies?.first(where: { $0.ticker == ticker }) {
                return (theme, company)
            }
        }
        return nil
    }

    private var company: RotationCompany? { companyMatch?.company }
    private var parentTheme: RotationTheme? { companyMatch?.theme ?? rotationTheme }

    private var delta: RankingDelta? {
        store.snapshot?.rankingDelta?[ticker]
            ?? store.snapshot?.assetRanking?.first { $0.ticker == ticker }
    }

    private var themeCompanies: [RotationCompany] {
        parentTheme?.companies ?? []
    }

    var body: some View {
        VStack(spacing: 0) {
            inspectorChrome
            if let parent = parentTheme, company != nil {
                Button {
                    if let themeTicker = parent.ticker {
                        store.showAsset(themeTicker)
                    }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "arrow.uturn.backward")
                        Text("Volver a \(parent.theme ?? parent.ticker ?? "tema")")
                        Spacer(minLength: 0)
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(NexusTheme.accent)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Volver a \(parent.theme ?? parent.ticker ?? "tema")")
            }
            if rotationTheme != nil && company == nil {
                inspectorSectionPicker
                .padding(.horizontal, 16)
                .padding(.bottom, 10)
                .help("Cambia entre resumen técnico, cesto de empresas, noticias y reglas.")
            }
            Divider().opacity(0.2)
            ScrollView {
                VStack(alignment: .leading, spacing: NexusLayout.spacing) {
                    if showSummaryTab {
                    if isFxPair {
                        fxInspectorPlan
                    }
                    compactInspectorSummary
                    sparklineCard
                    }

                    if showCompaniesTab {
                    if !themeCompanies.isEmpty, company == nil {
                        themeBasketCard(themeCompanies)
                    } else if let names = rotationTheme?.names, !names.isEmpty, company == nil {
                        VStack(alignment: .leading, spacing: 8) {
                            NexusSectionHeader(title: "Empresas representativas")
                            FlowChips(items: names)
                        }
                        .nexusCard()
                    } else if rotationTheme != nil, company == nil {
                        VStack(alignment: .leading, spacing: 6) {
                            NexusSectionHeader(title: "Empresas del tema")
                            Text("El motor no ha recibido todavía el desglose de empresas. Actualiza los datos para cargarlo.")
                                .font(.caption)
                                .foregroundStyle(NexusTheme.muted)
                        }
                        .nexusCard()
                    }

                    if company != nil, let parent = parentTheme {
                        VStack(alignment: .leading, spacing: 6) {
                            NexusSectionHeader(title: "Contexto del tema")
                            NexusKVRow(label: "Tema", value: parent.theme ?? parent.ticker ?? "—")
                            NexusKVRow(label: "Grupo", value: parent.group ?? "—")
                            NexusKVRow(label: "Señal sector", value: parent.signal ?? "—")
                            NexusKVRow(label: "Score ETF", value: parent.score.map { String(format: "%.0f" , $0) } ?? "—")
                        }
                        .nexusCard()
                    }

                    } // showCompaniesTab

                    if showMethodTab {
                    VStack(alignment: .leading, spacing: 8) {
                        NexusSectionHeader(
                            title: "Cómo se decide",
                            help: "Reglas técnicas internas. No son una recomendación de inversión ni sustituyen el bloqueo operativo."
                        )
                        ForEach(methodologyLines, id: \.self) { line in
                            Text("• \(line)")
                                .font(.caption)
                                .foregroundStyle(NexusTheme.muted)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Text(methodologyFooter)
                            .font(.caption2)
                            .foregroundStyle(NexusTheme.warn)
                            .padding(.top, 2)
                    }
                    .nexusCard()
                    }

                    if showNewsTab {
                    if relatedNews.isEmpty {
                        NexusEmptyState(
                            title: "Sin noticias relacionadas",
                            detail: "No hay titulares vinculados a este tema o empresa en la captura actual.",
                            symbol: "newspaper"
                        )
                    } else {
                        VStack(alignment: .leading, spacing: 8) {
                            NexusSectionHeader(
                                title: "Noticias relacionadas",
                                detail: "\(relatedNews.count)",
                                help: "Titulares que mencionan empresas o temas del sector. Coincidencia contextual, no causalidad."
                            )
                            ForEach(relatedNews.prefix(8)) { item in
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
                                        Text("Titular · relación contextual, no causalidad.")
                                            .font(.caption2)
                                            .foregroundStyle(NexusTheme.muted)
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .contentShape(Rectangle())
                                }
                                .buttonStyle(.plain)
                                if item.id != relatedNews.prefix(8).last?.id {
                                    Divider().opacity(0.12)
                                }
                            }
                        }
                        .nexusCard()
                    }
                    }

                    if showSummaryTab, !isFxPair {
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
                }
                .padding(16)
            }
            .scrollContentBackground(.hidden)
        }
        .background(NexusTheme.inspector)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .clipped()
        .onChange(of: ticker) { _, _ in
            inspectorTab = "resumen"
        }
    }

    private var inspectorChrome: some View {
        HStack(alignment: .center, spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text(headerTitle)
                    .font(.headline.weight(.bold))
                    .lineLimit(1)
                Text(headerSubtitle)
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
                    .lineLimit(2)
            }
            .frame(minWidth: 0, maxWidth: .infinity, alignment: .leading)
            .accessibilityElement(children: .combine)
            NexusToolbarButton(
                systemImage: store.isWatched(ticker) ? "star.fill" : "star",
                label: store.isWatched(ticker) ? "Quitar de seguimiento" : "Añadir a seguimiento",
                helpText: store.isWatched(ticker) ? "Quitar de seguimiento" : "Añadir a seguimiento (máximo 8)"
            ) {
                Task { await store.toggleWatchlist(ticker) }
            }
            .layoutPriority(2)
            NexusActionButton(
                title: "Cerrar",
                systemImage: "xmark",
                helpText: "Cerrar detalle (Esc)"
            ) {
                store.closeAssetInspector()
            }
            .layoutPriority(3)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(NexusTheme.inspector)
    }

    private var inspectorSectionPicker: some View {
        ViewThatFits(in: .horizontal) {
            Picker("Sección", selection: $inspectorTab) {
                inspectorSectionOptions
            }
            .pickerStyle(.segmented)

            Picker("Sección", selection: $inspectorTab) {
                inspectorSectionOptions
            }
            .pickerStyle(.menu)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    @ViewBuilder
    private var inspectorSectionOptions: some View {
        Text("Resumen").tag("resumen")
        Text("Empresas").tag("empresas")
        Text("Noticias").tag("noticias")
        Text("Metodología").tag("metodo")
    }

    private var isFxPair: Bool { ticker == "EURUSD" || ticker == "USDEUR" }

    private var isCurrencyPair: Bool {
        [
            "EURUSD", "USDEUR", "EURCAD", "USDCAD", "GBPUSD",
            "EURGBP", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD",
        ].contains(ticker)
    }

    private var priceDigits: Int {
        if ticker == "USDJPY" { return 3 }
        return isCurrencyPair ? 5 : 2
    }

    private var fxInspectorPlan: some View {
        let plan = store.snapshot?.forex?.plan
        return NexusStanceCard(
            stance: plan?.stance ?? "ESPERAR",
            buy: plan?.buy ?? "Nada ahora",
            verdict: plan?.verdict ?? "Esperar a una lectura completa del par.",
            doing: plan?.doing ?? "Confirmar tendencia y permiso operativo.",
            avoiding: plan?.avoiding ?? "No operar este par por un score aislado.",
            changes: plan?.changes,
            help: "Mismo veredicto que en Forex y oro. 50/100 es neutro, no falta de datos."
        )
        .environment(\.nexusBreakpoint, .narrow)
    }

    private var dualFxStrengthCard: some View {
        let strength = store.snapshot?.forex?.strength
        let highlighted = ticker == "USDEUR" ? strength?.usd : strength?.eur
        return VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "Fortaleza del par",
                help: "Cada pata usa precio, medias y momentum. 50 es neutro. 0 solo si el cálculo da debilidad real, no por falta de score."
            )
            fxStrengthRow("Euro", strength?.eur, highlight: ticker == "EURUSD")
            fxStrengthRow("Dólar", strength?.usd, highlight: ticker == "USDEUR")
            HStack {
                Text(highlighted.map { "\(Int($0.rounded()))" } ?? "—")
                    .font(.system(size: 26, weight: .bold, design: .rounded))
                    .foregroundStyle(scoreColor(for: highlighted.map { Int($0.rounded()) }))
                Text("/ 100 · \(ticker == "USDEUR" ? "dólar" : "euro")")
                    .foregroundStyle(NexusTheme.muted)
                Spacer()
                ToneBadge(tone: fxActionBadge, label: fxActionBadge)
            }
            Text(store.snapshot?.forex?.dual?[ticker == "USDEUR" ? "usd_view" : "eur_view"] ?? "Sin vista direccional.")
                .font(.caption)
                .foregroundStyle(NexusTheme.muted)
                .lineLimit(2)
        }
    }

    private func fxStrengthRow(_ label: String, _ value: Double?, highlight: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(LocalizedStringKey(label))
                    .font(.caption.weight(highlight ? .bold : .regular))
                Spacer()
                Text(value.map { String(format: "%.0f", $0) } ?? "sin dato")
                    .font(.caption.monospacedDigit().weight(.semibold))
                    .foregroundStyle(value == nil ? NexusTheme.muted : scoreColor(for: value.map { Int($0.rounded()) }))
            }
            NexusScoreBar(value: value, showValue: false)
        }
    }

    private var compactInspectorSummary: some View {
        VStack(alignment: .leading, spacing: 10) {
            if isFxPair {
                dualFxStrengthCard
            } else {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(scoreValue.map(String.init) ?? "—")
                        .font(.system(size: 28, weight: .bold, design: .rounded))
                        .foregroundStyle(scoreColor)
                    Text("/ 100")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                    NexusScoreBar(value: scoreValue.map(Double.init), showValue: false)
                        .frame(maxWidth: 160)
                    Spacer(minLength: 8)
                    ToneBadge(
                        tone: company != nil
                            ? companyTechnicalTone(company?.action, allowsEntry: store.snapshot?.sessionPlan?.allowsEntry == true)
                            : actionValue,
                        label: actionValue
                    )
                }
                if let delta {
                    HStack {
                        Label(deltaText(delta.scoreDelta), systemImage: deltaSymbol(delta.scoreDelta))
                        Spacer()
                        if let rank = delta.rank {
                            Text("Puesto \(rank)\(rankChange(delta))")
                        }
                    }
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(deltaColor(delta.scoreDelta))
                }
            }

            LazyVGrid(
                columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)],
                alignment: .leading,
                spacing: 6
            ) {
                NexusKVRow(label: "Precio", value: number(metrics?.price, digits: priceDigits))
                NexusKVRow(label: "Tendencia", value: company?.trend ?? score?.trend ?? rotationTheme?.trend ?? inferredTrend)
                if company == nil {
                    NexusKVRow(label: "Media 20", value: number(metrics?.ma20, digits: priceDigits), help: "Promedio de las últimas 20 sesiones.")
                    NexusKVRow(label: "Media 50", value: number(metrics?.ma50, digits: priceDigits), help: "Promedio de las últimas 50 sesiones.")
                    NexusKVRow(label: "Media 200", value: number(metrics?.ma200, digits: priceDigits), help: "Referencia de tendencia de largo plazo.")
                }
                NexusKVRow(
                    label: "Mom 1M",
                    value: formatPct(score?.momentum1m ?? company?.momentum1m ?? rotationTheme?.momentum1m ?? metrics?.momentum1m)
                )
                NexusKVRow(
                    label: "Mom 3M",
                    value: formatPct(score?.momentum3m ?? company?.momentum3m ?? rotationTheme?.momentum3m ?? metrics?.momentum3m)
                )
                NexusKVRow(
                    label: "Vol 20d",
                    value: formatPct(score?.volatility20d ?? company?.volatility20d ?? metrics?.volatility20d),
                    help: "Variación anualizada reciente. Una cifra alta implica mayor incertidumbre y menor tamaño prudente."
                )
            }
        }
        .nexusCard()
    }

    private var fxActionBadge: String {
        store.snapshot?.forex?.plan?.stance ?? store.snapshot?.forex?.signal?.action ?? actionValue
    }

    private var usesTabs: Bool { rotationTheme != nil && company == nil }
    private var showSummaryTab: Bool { !usesTabs || inspectorTab == "resumen" }
    private var showCompaniesTab: Bool { !usesTabs || inspectorTab == "empresas" }
    private var showNewsTab: Bool { !usesTabs || inspectorTab == "noticias" }
    private var showMethodTab: Bool { !usesTabs || inspectorTab == "metodo" }

    private var sparklinePoints: [SparklinePoint] {
        store.snapshot?.sparklines?[ticker]
            ?? store.snapshot?.sparklines?["^\(ticker)"]
            ?? []
    }

    private var sparklineCard: some View {
        NexusSparklineCard(
            title: "Precio",
            help: "Elige intervalo y rango; pulsa y arrastra para recorrer OHLCV, pellizca para ampliar y desplaza horizontalmente. Los puntos son titulares ligados a este activo, no órdenes.",
            points: sparklinePoints,
            minHeight: 300,
            valueDigits: priceDigits,
            ticker: ticker,
            news: newsLinked(
                to: ticker,
                items: store.snapshot?.news?.items ?? [],
                extra: relatedNews + (
                    ticker == "XAUUSD"
                        ? newsLinked(to: "GLD", items: store.snapshot?.news?.items ?? [])
                        : []
                )
            ),
            spyPoints: store.snapshot?.sparklines?["SPY"] ?? [],
            onOpenNews: { item in
                store.selectedNewsID = item.id
                store.selected = .news
            }
        )
    }

    @ViewBuilder
    private func themeBasketCard(_ companies: [RotationCompany]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            NexusSectionHeader(
                title: "Empresas del tema",
                detail: "\(companies.count)",
                help: "Fuerza técnica del cesto. No es una orden: COMPRAR operativo vive en Resumen."
            )
            if let represents = parentTheme?.represents {
                Text(represents.capitalized)
                    .font(.caption)
                    .foregroundStyle(NexusTheme.muted)
            }

            HStack(spacing: 8) {
                basketStat("Fuertes", "\(basketCount("FUERTE"))", NexusTheme.good)
                basketStat("Observar", "\(basketCount("OBSERVAR"))", NexusTheme.warn)
                basketStat("Débiles", "\(basketCount("DEBIL"))", NexusTheme.bad)
                basketStat("Score medio", basketAvgScore, NexusTheme.accent)
            }

            HStack {
                Text("EMPRESA")
                    .frame(maxWidth: .infinity, alignment: .leading)
                Text("SEÑAL / SCORE")
                    .frame(width: 112, alignment: .trailing)
            }
            .font(.caption2.weight(.bold))
            .foregroundStyle(NexusTheme.muted)
            .padding(.top, 2)

            ForEach(companies) { company in
                Button {
                    if let companyTicker = company.ticker {
                        store.showAsset(companyTicker)
                    }
                } label: {
                    NexusCompanyRow(
                        company: company,
                        allowsEntry: store.snapshot?.sessionPlan?.allowsEntry == true
                    )
                }
                .buttonStyle(.plain)
                if company.id != companies.last?.id {
                    Divider().opacity(0.10)
                }
            }
        }
        .nexusCard()
    }

    private func basketStat(_ title: String, _ value: String, _ tone: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(LocalizedStringKey(title))
                .font(.caption2)
                .foregroundStyle(NexusTheme.muted)
            Text(value)
                .font(.caption.monospacedDigit().weight(.bold))
                .foregroundStyle(tone)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(8)
        .background(NexusTheme.cardInner.opacity(0.85))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func basketCount(_ action: String) -> Int {
        let aliases: [String: [String]] = [
            "FUERTE": ["FUERTE", "COMPRAR"],
            "OBSERVAR": ["OBSERVAR", "ESPERAR"],
            "DEBIL": ["DEBIL", "DÉBIL", "VENDER"],
        ]
        let keys = Set(aliases[action] ?? [action])
        return themeCompanies.filter { keys.contains(($0.action ?? "").uppercased()) }.count
    }

    private var basketAvgScore: String {
        let scores = themeCompanies.compactMap(\.score)
        guard !scores.isEmpty else { return "—" }
        let avg = Double(scores.reduce(0, +)) / Double(scores.count)
        return String(format: "%.0f", avg)
    }

    private var headerTitle: String {
        if let company {
            return company.ticker ?? ticker
        }
        return ticker
    }

    private var headerSubtitle: String {
        if let company {
            return "\(company.name ?? ticker) · \(parentTheme?.theme ?? "Rotación")"
        }
        return score?.label ?? rotationTheme?.theme ?? assetName
    }

    private var methodologyLines: [String] {
        if company != nil {
            return [
                "Partimos de score 50/100.",
                "Tendencia alcista +20; bajista −20 (precio frente a medias).",
                "Momentum 1M y 3M pesan según magnitud: un +7% cuenta más que un +0,3%.",
                "FUERTE si score ≥ 70 es lectura técnica, no una orden. OBSERVAR 36–69. DÉBIL si ≤ 35.",
            ]
        }
        if rotationTheme != nil {
            return [
                "El score del tema usa precio vs MA20/50/200 y momentum 1M/3M proporcional a su tamaño.",
                "Se compara el momentum 1M del ETF con el de SPY (fuerza relativa).",
                "«Entrada clara de flujo» = momentum 1M > 1,5% y batir a SPY por más de 1 pp.",
                "Los líderes se eligen por momentum 3M frente a SPY, no por el cajón Tecnología.",
                "Las empresas del cesto se evalúan por separado: FUERTE / OBSERVAR / DÉBIL, no COMPRAR.",
            ]
        }
        return [
            "El score operativo combina régimen, riesgo, activos y filtros (noticias/calendario).",
            "COMPRAR / ESPERAR / REDUCIR del resumen no equivale a la fuerza técnica de una empresa suelta.",
            "Un bloqueo de calendario o riesgo anula entradas aunque el score técnico sea alto.",
        ]
    }

    private var methodologyFooter: String {
        if company != nil {
            return "Es una lectura técnica del ticker, no una orden. Respeta siempre el bloqueo global y la asignación operativa."
        }
        return "El conglomerado (ETF) y sus empresas pueden discrepar: un sector en flujo no implica comprar todas sus componentes."
    }

    private var relatedNews: [NewsItem] {
        let items = store.snapshot?.news?.items ?? []
        let names: [String]
        let tickers: [String]
        let eventTopics: Set<String> = ["Fed/tipos", "Inflación", "Recesión/empleo"]
        let themeTopics: Set<String>
        if let company {
            names = [company.name].compactMap { $0?.lowercased() }
            tickers = [company.ticker].compactMap { $0?.lowercased() }
            themeTopics = []
        } else {
            names = (rotationTheme?.names ?? []).map { $0.lowercased() }
            tickers = (rotationTheme?.companies ?? []).compactMap { $0.ticker?.lowercased() }
            themeTopics = Set(rotationTheme?.newsTopics ?? []).intersection(eventTopics)
        }
        guard !names.isEmpty || !tickers.isEmpty || !themeTopics.isEmpty else { return [] }
        return items.filter { item in
            let blob = [item.title, item.summary]
                .compactMap { $0?.lowercased() }
                .joined(separator: " ")
            if names.contains(where: { blob.contains($0) }) { return true }
            if tickers.contains(where: { blob.contains($0) }) { return true }
            if let linked = item.linkedCompanies, !Set(linked.map { $0.lowercased() }).isDisjoint(with: Set(tickers)) {
                return true
            }
            guard !themeTopics.isEmpty else { return false }
            let itemEvents = Set(item.eventTopics ?? []).union(Set(item.linkedTopics ?? []).intersection(eventTopics))
            return !itemEvents.isDisjoint(with: themeTopics)
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
        case "GLD": return "Oro ETF"
        case "XAUUSD": return "Oro spot"
        case "UUP": return "Dólar"
        case "EURUSD": return "Euro / dólar"
        case "USDEUR": return "Dólar / euro"
        case "EURCAD": return "Euro / dólar canadiense"
        case "USDCAD": return "Dólar / dólar canadiense"
        case "GBPUSD": return "Libra / dólar"
        case "EURGBP": return "Euro / libra"
        case "USDJPY": return "Dólar / yen"
        case "USDCHF": return "Dólar / franco suizo"
        case "AUDUSD": return "Dólar australiano / dólar"
        case "NZDUSD": return "Dólar neozelandés / dólar"
        case "CASH": return "Liquidez"
        case "EWJ": return "Japón"
        case "FXI": return "China"
        case "AAXJ": return "Asia emergente"
        case "EWY": return "Corea del Sur"
        case "EWP": return "España / IBEX"
        default: return ticker
        }
    }

    private var inferredTrend: String {
        guard let price = metrics?.price, let ma50 = metrics?.ma50 else { return "—" }
        return price >= ma50 ? "Sobre MA50" : "Bajo MA50"
    }

    private var scoreColor: Color {
        scoreColor(for: scoreValue)
    }

    private func scoreColor(for value: Int?) -> Color {
        guard let value else { return NexusTheme.muted }
        if value >= 65 { return NexusTheme.good }
        if value >= 45 { return NexusTheme.warn }
        return NexusTheme.bad
    }

    private var guidance: (doing: String, avoiding: String, changes: String) {
        if company != nil {
            return (
                "Es fuerza técnica del ticker, no una orden. El permiso está en Resumen.",
                "No comprar porque el score sea alto ni vender porque sea bajo.",
                "El bloqueo operativo y la asignación mandan sobre esta lectura."
            )
        }
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

    private var scoreValue: Int? {
        if let companyScore = company?.score { return companyScore }
        if ticker == "EURUSD", let eur = store.snapshot?.forex?.strength?.eur {
            return Int(eur.rounded())
        }
        if ticker == "USDEUR", let usd = store.snapshot?.forex?.strength?.usd {
            return Int(usd.rounded())
        }
        if let score = score?.score { return score }
        return rotationTheme?.score.map { Int($0.rounded()) }
    }

    private var actionValue: String {
        if isFxPair {
            return store.snapshot?.forex?.plan?.stance ?? store.snapshot?.forex?.signal?.action ?? "ESPERAR"
        }
        if let action = company?.action {
            return companyTechnicalLabel(action, allowsEntry: store.snapshot?.sessionPlan?.allowsEntry == true)
        }
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

    private func inverse(_ value: Double?) -> Double? {
        guard let value, value != 0 else { return nil }
        return 1 / value
    }

    private func inverseReturn(_ percent: Double?) -> Double? {
        guard let percent else { return nil }
        let factor = 1 + percent / 100
        guard factor > 0 else { return nil }
        return (1 / factor - 1) * 100
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

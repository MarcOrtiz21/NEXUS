import SwiftUI

private enum GoldFactorSort: String, CaseIterable, Identifiable {
    case family = "Familia"
    case indicator = "Indicador"
    case period = "Periodo"
    case quality = "Calidad"
    case contribution = "Impacto de familia"
    var id: String { rawValue }
}

private struct GoldFactorRow: Identifiable {
    let id: String
    let group: GoldFactorGroup
    let detail: GoldFactorDetail
}

struct GoldFactorTable: View {
    let groups: [GoldFactorGroup]
    let revisions: GoldRevisionReport?
    @Environment(\.nexusContentWidth) private var contentWidth
    @State private var expanded = false
    @State private var sort: GoldFactorSort = .family
    @State private var descending = false
    @State private var query = ""
    @State private var onlyIssues = false

    private var rows: [GoldFactorRow] {
        let all = groups.flatMap { group in
            (group.details ?? []).enumerated().map { index, detail in
                GoldFactorRow(id: "\(group.id)-\(detail.metricKey ?? detail.id)-\(index)", group: group, detail: detail)
            }
        }
        return all.filter { row in
            let text = "\(row.group.label ?? "") \(row.detail.label ?? "") \(row.detail.source ?? "")"
            let matches = query.isEmpty || text.localizedCaseInsensitiveContains(query)
            return matches && (!onlyIssues || row.detail.available != true || row.detail.quality != "OK")
        }.sorted { left, right in
            let a: String
            let b: String
            switch sort {
            case .family: a = left.group.label ?? ""; b = right.group.label ?? ""
            case .indicator: a = left.detail.label ?? ""; b = right.detail.label ?? ""
            case .period: a = left.detail.asOf ?? ""; b = right.detail.asOf ?? ""
            case .quality: a = quality(left.detail); b = quality(right.detail)
            case .contribution:
                let a = abs(left.group.shortContribution ?? 0), b = abs(right.group.shortContribution ?? 0)
                if a != b { return descending ? a > b : a < b }
                return left.id < right.id
            }
            if a == b { return left.id < right.id }
            return descending ? a > b : a < b
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            DisclosureGroup(isExpanded: $expanded) {
                VStack(alignment: .leading, spacing: 12) {
                    controls
                    Text("\(rows.count) indicadores · el impacto pertenece a la familia y se repite como contexto; las filas no se suman.")
                        .font(.caption)
                        .foregroundStyle(NexusTheme.muted)
                    if rows.isEmpty {
                        NexusEmptyState(title: "Sin indicadores coincidentes", detail: "Cambia la búsqueda o el filtro de calidad.", symbol: "line.3.horizontal.decrease.circle")
                    } else if contentWidth >= 1180 {
                        wideTable
                    } else {
                        LazyVStack(spacing: 8) {
                            ForEach(rows) { row in compactRow(row) }
                        }
                    }
                }
                .padding(.top, 12)
            } label: {
                NexusSectionHeader(title: "DATOS Y FUENTES", detail: "tabla de indicadores")
            }
            .accessibilityIdentifier("gold.factorTable")
        }
        .nexusCard()
    }

    private var controls: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) {
                search.frame(minWidth: 200, maxWidth: .infinity)
                sorting
                Toggle("Con incidencias", isOn: $onlyIssues).toggleStyle(.checkbox)
            }
            VStack(alignment: .leading, spacing: 10) {
                search
                HStack(spacing: 12) {
                    sorting
                    Toggle("Con incidencias", isOn: $onlyIssues).toggleStyle(.checkbox)
                }
            }
        }
        .font(.caption)
    }

    private var search: some View {
        TextField("Buscar indicador, familia o fuente", text: $query)
            .textFieldStyle(.roundedBorder)
            .accessibilityLabel("Buscar factores de oro")
    }

    private var sorting: some View {
        HStack(spacing: 8) {
            Picker("Ordenar", selection: $sort) {
                ForEach(GoldFactorSort.allCases) { Text($0.rawValue).tag($0) }
            }
            .frame(width: 220)
            Button { descending.toggle() } label: {
                Image(systemName: descending ? "arrow.down" : "arrow.up")
            }
            .help(descending ? "Orden descendente" : "Orden ascendente")
            .accessibilityLabel(descending ? "Cambiar a orden ascendente" : "Cambiar a orden descendente")
        }
    }

    private var wideTable: some View {
        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 10) {
            GridRow {
                header("Indicador / familia").frame(width: columnWidth(0), alignment: .leading)
                header("Valor").frame(width: columnWidth(1), alignment: .leading)
                header("Periodo").frame(width: columnWidth(2), alignment: .leading)
                header("Publicación conocida").frame(width: columnWidth(3), alignment: .leading)
                header("Fuente").frame(width: columnWidth(4), alignment: .leading)
                header("Calidad").frame(width: columnWidth(5), alignment: .leading)
                header("Familia · 1M / 3M").frame(width: columnWidth(6), alignment: .leading)
            }
            Divider().gridCellColumns(7)
            ForEach(rows) { row in
                GridRow {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(row.detail.label ?? "Indicador").fontWeight(.semibold)
                        Text(row.group.label ?? "Familia").foregroundStyle(NexusTheme.muted)
                    }
                    .frame(width: columnWidth(0), alignment: .leading)
                    Text(row.detail.display ?? "—").monospacedDigit()
                    Text(day(row.detail.asOf)).monospacedDigit()
                    Text(publication(row)).monospacedDigit()
                    Text(row.detail.source ?? "No registrada")
                        .foregroundStyle(NexusTheme.muted)
                        .frame(width: columnWidth(4), alignment: .leading)
                    Text(quality(row.detail)).foregroundStyle(qualityColor(row.detail))
                    Text(impact(row.group)).monospacedDigit()
                }
                .accessibilityElement(children: .combine)
                Divider().gridCellColumns(7)
            }
        }
        .font(.caption)
    }

    private func columnWidth(_ index: Int) -> CGFloat {
        // Reserve card padding and six gaps; share the remaining width explicitly.
        let proportions: [CGFloat] = [0.23, 0.09, 0.12, 0.14, 0.18, 0.12, 0.12]
        let padding = 2 * (NexusLayout.pagePadding + NexusLayout.cardPadding)
        return max(0, contentWidth - padding - 72) * proportions[index]
    }

    private func compactRow(_ row: GoldFactorRow) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .firstTextBaseline) {
                Text(row.detail.label ?? "Indicador").fontWeight(.semibold)
                Spacer()
                Text(row.detail.display ?? "—").monospacedDigit().fontWeight(.semibold)
            }
            Text(row.group.label ?? "Familia").foregroundStyle(NexusTheme.accent)
            NexusKVRow(label: "Periodo · publicación", value: "\(day(row.detail.asOf)) · \(publication(row))")
            Text("Fuente: \(row.detail.source ?? "no registrada")")
                .foregroundStyle(NexusTheme.muted)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Text(quality(row.detail)).foregroundStyle(qualityColor(row.detail))
                Spacer()
                Text("Familia 1M / 3M: \(impact(row.group))").monospacedDigit()
            }
        }
        .font(.caption)
        .padding(10)
        .background(NexusTheme.cardInner, in: RoundedRectangle(cornerRadius: 9))
        .accessibilityElement(children: .combine)
    }

    private func publication(_ row: GoldFactorRow) -> String {
        if let release = row.detail.releaseAt { return day(release) }
        let source = row.detail.source?.replacingOccurrences(of: "FRED:", with: "")
        let series = revisions?.series?.first { $0.seriesID == source }
        if series?.status == "OK", let observation = series?.observations?.first(where: { $0.period == day(row.detail.asOf) }) {
            return day(observation.knownReleaseAt)
        }
        return "No verificada"
    }

    private func impact(_ group: GoldFactorGroup) -> String {
        guard group.scoreEnabled == true else { return "Contexto" }
        let short = group.shortContribution.map { String(format: "%+.1f", $0) } ?? "—"
        let medium = group.mediumContribution.map { String(format: "%+.1f", $0) } ?? "—"
        return "\(short) / \(medium)"
    }

    private func day(_ value: String?) -> String { value.map { String($0.prefix(10)) } ?? "—" }
    private func quality(_ detail: GoldFactorDetail) -> String {
        if detail.available != true { return "Sin dato" }
        switch detail.quality {
        case "OK": return "Actualizado"
        case "STALE": return "Caché caducada"
        case "ERROR": return "Error de fuente"
        default: return "Sin verificar"
        }
    }
    private func qualityColor(_ detail: GoldFactorDetail) -> Color {
        detail.available == true && detail.quality == "OK" ? NexusTheme.muted : NexusTheme.warn
    }
    private func header(_ text: String) -> some View {
        Text(text).fontWeight(.semibold).foregroundStyle(NexusTheme.muted)
    }
}

struct GoldRevisionCard: View {
    let report: GoldRevisionReport?
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            DisclosureGroup(isExpanded: $expanded) {
                VStack(alignment: .leading, spacing: 12) {
                    Text(report?.methodology ?? "Actualiza los datos para consultar primeras publicaciones y revisiones conocidas.")
                        .foregroundStyle(NexusTheme.muted)
                    Text("Corte \(report?.asOf ?? "—") · cambios en la unidad original · publicación con precisión de día")
                        .foregroundStyle(NexusTheme.muted)
                    ForEach(report?.series ?? []) { series in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text("\(series.label ?? "Serie") · \(series.unit ?? "")").fontWeight(.semibold)
                                Spacer()
                                Text(series.status == "OK" ? "ALFRED" : series.status == "STALE" ? "CACHÉ CADUCADA" : "SIN DATOS")
                                    .foregroundStyle(series.status == "OK" ? NexusTheme.accent : NexusTheme.warn)
                            }
                            ForEach(series.observations ?? []) { observation in
                                ViewThatFits(in: .horizontal) {
                                    HStack(spacing: 18) {
                                        Text(observation.period ?? "—").monospacedDigit()
                                        values(observation)
                                        Spacer()
                                        dates(observation)
                                    }
                                    VStack(alignment: .leading, spacing: 5) {
                                        Text(observation.period ?? "—").monospacedDigit()
                                        values(observation)
                                        dates(observation)
                                    }
                                }
                                .accessibilityElement(children: .combine)
                            }
                        }
                        .padding(10)
                        .background(NexusTheme.cardInner, in: RoundedRectangle(cornerRadius: 9))
                    }
                }
                .font(.caption)
                .padding(.top, 12)
            } label: {
                NexusSectionHeader(title: "REVISIONES MACRO", detail: "primera publicación y dato conocido")
            }
            .accessibilityIdentifier("gold.revisions")
        }
        .nexusCard()
    }

    private func values(_ row: GoldRevisionObservation) -> some View {
        HStack(spacing: 12) {
            Text("Inicial \(number(row.initialValue))")
            Text("Conocido \(number(row.knownValue))")
            Text("Δ \(row.delta.map { String(format: "%+.3f", $0) } ?? "—")")
        }
        .monospacedDigit()
    }
    private func dates(_ row: GoldRevisionObservation) -> some View {
        Text("Publicaciones \(row.initialReleaseAt ?? "—") → \(row.knownReleaseAt ?? "—")")
            .foregroundStyle(NexusTheme.muted)
    }
    private func number(_ value: Double?) -> String { value.map { String(format: "%.3f", $0) } ?? "—" }
}

struct GoldBacktestComparisonDetails: View {
    let result: GoldBacktestHorizon?
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let overlap = result?.overlap {
                Text("\(overlap.nonOverlappingCount ?? 0) cortes sin solapamiento · hasta \(overlap.maxConcurrentWindows ?? 1) ventanas simultáneas")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
                Text("Estabilidad: \(result?.stability?.winningFolds ?? 0) / \(result?.stability?.folds ?? 0) ventanas mejoran las cuatro referencias")
                    .font(.caption2)
                    .foregroundStyle(NexusTheme.muted)
            }
            if result?.baselineConstant != nil {
                DisclosureGroup("Referencias e incertidumbre", isExpanded: $expanded) {
                    VStack(alignment: .leading, spacing: 10) {
                        baseline("50% constante", key: "constant", metrics: result?.baselineConstant)
                        baseline("Frecuencia del entrenamiento", key: "historical_frequency", metrics: result?.baselineHistoricalFrequency)
                        baseline("Momentum", key: "momentum", metrics: result?.baselineMomentum)
                        baseline("Dólar y tipos reales", key: "dollar_real_yield", metrics: result?.baselineDollarRealYield)
                        Text("Δ Brier = NEXUS − referencia. Un intervalo que cruza cero no establece una mejora. IC 95% aproximado por bloques de cortes consecutivos.")
                            .foregroundStyle(NexusTheme.muted)
                            .fixedSize(horizontal: false, vertical: true)
                        if let candidates = result?.candidates, !candidates.isEmpty {
                            Divider()
                            Text("CANDIDATOS WALK-FORWARD · FUERA DEL SCORE").fontWeight(.semibold)
                            candidate("Calibración hacia la base", candidates["calibrated"])
                            candidate("Pesos aprendidos", candidates["learned"])
                            candidate("Pesos aprendidos + régimen 2022", candidates["learned_regime"])
                            candidate("Tendencia ajustada por volatilidad", candidates["trend"])
                            candidate("Señales en cambios", candidates["compact_logistic"])
                            candidate("Rendimiento esperado", candidates["return_compact"])
                            candidate("Rendimiento sobre la tendencia", candidates["return_trend"])
                            Text("Ajustados en cada ventana solo con resultados vencidos; las señales en cambios eligen su regularización con validación anidada y necesitan cinco años de entrenamiento. El régimen 2022 es una hipótesis elegida a posteriori. Ninguno puntúa sin superar las cuatro referencias con intervalo por debajo de cero.")
                                .foregroundStyle(NexusTheme.muted)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        if let revision = result?.revisionDiagnostics {
                            Divider()
                            Text("PRIMERA PUBLICACIÓN / REVISIÓN CONOCIDA").fontWeight(.semibold)
                            Text("Brier \(number(revision.initialRelease?.brierScore)) / \(number(revision.knownRevision?.brierScore))")
                            Text("\(revision.directionChanges ?? 0) cambios de dirección · Δ estimación media \(number(revision.meanProbabilityChangePp)) pp")
                                .foregroundStyle(NexusTheme.muted)
                        }
                    }
                    .padding(.top, 8)
                }
                .font(.caption)
            }
        }
    }

    private func baseline(_ title: String, key: String, metrics: GoldBacktestMetrics?) -> some View {
        let interval = result?.comparisons?[key]
        return VStack(alignment: .leading, spacing: 4) {
            NexusKVRow(label: title, value: "Brier \(number(metrics?.brierScore))")
            if let lower = interval?.lower, let upper = interval?.upper {
                Text("Δ \(number(interval?.deltaBrier)) · IC95% [\(number(lower)), \(number(upper))]")
                    .monospacedDigit()
                    .foregroundStyle(upper < 0 ? NexusTheme.good : NexusTheme.muted)
            } else {
                Text("Intervalo pendiente de muestra suficiente").foregroundStyle(NexusTheme.warn)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func candidate(_ title: String, _ item: GoldBacktestCandidate?) -> some View {
        let interval = item?.comparisons?["historical_frequency"]
        let constant = item?.comparisons?["constant"]
        return VStack(alignment: .leading, spacing: 4) {
            NexusKVRow(
                label: title,
                value: item?.passesBaselines == true ? "SUPERA REFERENCIAS" : "NO CONCLUYENTE"
            )
            Text("Brier \(number(item?.brierScore)) · Δ vs NEXUS \(number(item?.deltaBrierVsModel)) · precisión equilibrada \(item?.balancedAccuracy.map { String(format: "%.1f%%", $0 * 100) } ?? "—") · n \(item?.sampleSize.map(String.init) ?? "—")")
                .monospacedDigit()
            if let lower = interval?.lower, let upper = interval?.upper {
                Text("Δ vs frecuencia histórica · IC95% [\(number(lower)), \(number(upper))]")
                    .monospacedDigit()
                    .foregroundStyle(upper < 0 ? NexusTheme.good : NexusTheme.muted)
            }
            if let lower = constant?.lower, let upper = constant?.upper {
                Text("Δ vs 50% constante · IC95% [\(number(lower)), \(number(upper))]")
                    .monospacedDigit()
                    .foregroundStyle(upper < 0 ? NexusTheme.good : NexusTheme.muted)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func number(_ value: Double?) -> String { value.map { String(format: "%.3f", $0) } ?? "—" }
}

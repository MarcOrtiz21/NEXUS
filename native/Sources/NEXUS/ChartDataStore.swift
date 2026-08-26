import Foundation
import OSLog
import SwiftUI

extension Notification.Name {
    static let nexusSnapshotDidRefresh = Notification.Name("nexus.snapshot.didRefresh")
}

private let chartDataLogger = Logger(
    subsystem: "com.nexus.workstation",
    category: "ChartData"
)

struct ChartSeriesState {
    var ticker: String = ""
    var points: [SparklinePoint]
    var benchmark: [SparklinePoint]
    var interval: String = "1d"
    var range: String = "1y"
    var asOf: String?
    var source: String?
    var status: String?
    var revision: String?
    var timezone: String?
    var session: String?
    var adjusted: Bool?
    var adjustment: String?
    var marketState: String?
    var dataStatus: String?
    var loading = false
    var loadedRemote = false
    var errorMessage: String?
}

@MainActor
final class ChartDataStore: ObservableObject {
    @Published private var entries: [String: ChartSeriesState] = [:]

    private let client = NexusAPIClient()
    private var tasks: [String: Task<ChartSeriesPayload, Error>] = [:]
    private var requestIDs: [String: UUID] = [:]
    private var invalidationTask: Task<Void, Never>?

    init() {
        invalidationTask = Task { [weak self] in
            for await _ in NotificationCenter.default.notifications(named: .nexusSnapshotDidRefresh) {
                guard !Task.isCancelled else { return }
                await self?.refreshLoaded()
            }
        }
    }

    deinit {
        invalidationTask?.cancel()
    }

    func state(
        for ticker: String,
        interval: NexusChartInterval,
        range: NexusChartRange,
        fallback: [SparklinePoint],
        benchmark: [SparklinePoint]
    ) -> ChartSeriesState {
        let key = seriesKey(ticker, interval: interval, range: range)
        if let entry = entries[key] {
            return entry
        }
        return ChartSeriesState(
            ticker: normalized(ticker),
            points: fallback,
            benchmark: benchmark,
            interval: interval.rawValue,
            range: range.rawValue
        )
    }

    func load(
        ticker: String,
        interval: NexusChartInterval,
        range: NexusChartRange,
        fallback: [SparklinePoint],
        benchmark: [SparklinePoint],
        force: Bool = false
    ) async {
        let normalizedTicker = normalized(ticker)
        let key = seriesKey(normalizedTicker, interval: interval, range: range)
        guard !normalizedTicker.isEmpty else { return }

        if entries[key] == nil {
            entries[key] = ChartSeriesState(
                ticker: normalizedTicker,
                points: fallback,
                benchmark: benchmark,
                interval: interval.rawValue,
                range: range.rawValue,
                loading: true
            )
        } else {
            if entries[key]?.loadedRemote == true, !force { return }
            entries[key]?.loading = true
            entries[key]?.errorMessage = nil
        }

        let task: Task<ChartSeriesPayload, Error>
        let requestID: UUID
        let startedAt = Date()
        if let current = tasks[key], !force {
            task = current
            requestID = requestIDs[key] ?? UUID()
        } else {
            tasks[key]?.cancel()
            requestID = UUID()
            task = Task { [client] in
                try Task.checkCancellation()
                return try await client.fetchChart(
                    ticker: normalizedTicker,
                    interval: interval,
                    range: range,
                    refresh: force
                )
            }
            tasks[key] = task
            requestIDs[key] = requestID
        }

        do {
            let payload = try await task.value
            guard !Task.isCancelled, requestIDs[key] == requestID else { return }
            entries[key] = ChartSeriesState(
                ticker: normalizedTicker,
                points: payload.points,
                benchmark: payload.benchmark ?? benchmark,
                interval: payload.interval ?? "1d",
                range: payload.range ?? range.rawValue,
                asOf: payload.asOf,
                source: payload.source,
                status: payload.status,
                revision: payload.revision,
                timezone: payload.timezone,
                session: payload.session,
                adjusted: payload.adjusted,
                adjustment: payload.adjustment,
                marketState: payload.marketState,
                dataStatus: payload.dataStatus,
                loading: false,
                loadedRemote: true,
                errorMessage: nil
            )
            let elapsedMS = Date().timeIntervalSince(startedAt) * 1_000
            chartDataLogger.debug(
                "loaded \(normalizedTicker, privacy: .public) \(interval.rawValue, privacy: .public)/\(range.rawValue, privacy: .public): \(payload.points.count) points in \(elapsedMS, format: .fixed(precision: 1)) ms"
            )
        } catch is CancellationError {
            // Una petición más reciente ha sustituido a esta.
        } catch {
            if requestIDs[key] == requestID {
                entries[key]?.loading = false
                entries[key]?.errorMessage = error.localizedDescription
                chartDataLogger.error(
                    "failed \(normalizedTicker, privacy: .public) \(interval.rawValue, privacy: .public)/\(range.rawValue, privacy: .public): \(error.localizedDescription, privacy: .public)"
                )
            }
        }
        if requestIDs[key] == requestID {
            tasks[key] = nil
            requestIDs[key] = nil
        }
    }

    func retry(
        ticker: String,
        interval: NexusChartInterval,
        range: NexusChartRange,
        fallback: [SparklinePoint],
        benchmark: [SparklinePoint]
    ) async {
        await load(
            ticker: ticker,
            interval: interval,
            range: range,
            fallback: fallback,
            benchmark: benchmark,
            force: true
        )
    }

    func cancel(ticker: String, interval: NexusChartInterval, range: NexusChartRange) {
        let key = seriesKey(ticker, interval: interval, range: range)
        tasks[key]?.cancel()
        tasks[key] = nil
        requestIDs[key] = nil
        entries[key]?.loading = false
    }

    private func refreshLoaded() async {
        let loaded = entries
            .filter { $0.value.loadedRemote }
            .map(\.value)
        for state in loaded {
            guard let interval = NexusChartInterval(rawValue: state.interval),
                  let range = NexusChartRange(rawValue: state.range) else { continue }
            let key = seriesKey(state.ticker, interval: interval, range: range)
            entries[key]?.loadedRemote = false
            await load(
                ticker: state.ticker,
                interval: interval,
                range: range,
                fallback: state.points,
                benchmark: state.benchmark
            )
        }
    }

    private func normalized(_ ticker: String) -> String {
        ticker.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
    }

    private func seriesKey(
        _ ticker: String,
        interval: NexusChartInterval,
        range: NexusChartRange
    ) -> String {
        "\(normalized(ticker))|\(interval.rawValue)|\(range.rawValue)"
    }
}

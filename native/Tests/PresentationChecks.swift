import Foundation

/// Smoke test del código de producción sin XCTest (Command Line Tools no lo incluyen).
@main struct PresentationChecks {
    @MainActor static func main() async throws {
        do {
            try NativeSnapshotContractChecks.run(fixturePath: CommandLine.arguments[1])
        } catch {
            FileHandle.standardError.write(Data("Contrato nativo: \(error.localizedDescription)\n".utf8))
            exit(1)
        }
        precondition(PresentationPolicy.overviewSidebarWidth(availableWidth: 766) == nil)
        precondition(PresentationPolicy.overviewSidebarWidth(availableWidth: 1039) == nil)
        precondition(PresentationPolicy.overviewSidebarWidth(availableWidth: 1040) == 300)
        precondition(PresentationPolicy.overviewSidebarWidth(availableWidth: 1226) == 306.5)
        precondition(PresentationPolicy.overviewSidebarWidth(availableWidth: 1746) == 380)
        precondition(PresentationPolicy.vixPosition(15) == 0.25)
        precondition(PresentationPolicy.vixPosition(20) == 0.5)
        precondition(PresentationPolicy.vixPosition(30) == 0.75)
        precondition((0.25..<0.5).contains(PresentationPolicy.vixPosition(15.7)))
        precondition(PresentationPolicy.vixPosition(-1) == 0)
        precondition(PresentationPolicy.vixPosition(80) == 1)
        let now = Date(timeIntervalSince1970: 1000)
        precondition(!PresentationPolicy.reloadChart(status: "fresh", loadedAt: now.addingTimeInterval(-10), now: now))
        precondition(PresentationPolicy.reloadChart(status: "fresh", loadedAt: now.addingTimeInterval(-61), now: now))
        precondition(PresentationPolicy.reloadChart(status: "stale", loadedAt: now.addingTimeInterval(-3), now: now))
        precondition(!PresentationPolicy.reloadChart(status: "stale", loadedAt: now, now: now))
        precondition(PresentationPolicy.reloadChart(status: nil, loadedAt: nil, now: now))
        precondition(PresentationPolicy.denseChart(pointCount: 6065, width: 1600))
        precondition(!PresentationPolicy.denseChart(pointCount: 66, width: 820))
        var calls = 0
        let store = ChartDataStore(fetcher: { _, _, _, _ in
            calls += 1
            let status = calls == 1 ? "stale" : "fresh"
            return try JSONDecoder().decode(ChartSeriesPayload.self, from: Data("{\"ticker\":\"SMH\",\"points\":[],\"status\":\"\(status)\",\"as_of\":\"2026-10-08\",\"benchmark_as_of\":\"2026-10-09\"}".utf8))
        })
        await store.load(ticker: "SMH", interval: .oneDay, range: .threeMonths, fallback: [], benchmark: [])
        let result = store.state(for: "SMH", interval: .oneDay, range: .threeMonths, fallback: [], benchmark: [])
        precondition(calls == 2 && result.status == "fresh")
        precondition(result.asOf == "2026-10-08" && result.benchmarkAsOf == "2026-10-09")
        await store.load(ticker: "SMH", interval: .oneDay, range: .threeMonths, fallback: [], benchmark: [])
        precondition(calls == 2)
        print("Native presentation checks passed: Overview layout, VIX, density, expiry, stale-to-fresh and request reuse")
    }
}

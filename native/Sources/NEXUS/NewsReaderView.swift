import SwiftUI
import WebKit

struct NewsReaderView: View {
    let url: URL
    @StateObject private var model: NewsReaderModel

    init(url: URL) {
        self.url = url
        _model = StateObject(wrappedValue: NewsReaderModel(url: url))
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Button { model.goBack() } label: { Image(systemName: "chevron.left") }
                    .disabled(!model.canGoBack)
                    .help("Atrás")
                Button { model.goForward() } label: { Image(systemName: "chevron.right") }
                    .disabled(!model.canGoForward)
                    .help("Adelante")
                Button { model.reload() } label: { Image(systemName: "arrow.clockwise") }
                    .help("Recargar artículo")
                Divider().frame(height: 16)
                Button { model.decreaseText() } label: { Image(systemName: "textformat.size.smaller") }
                    .help("Reducir texto")
                Button { model.increaseText() } label: { Image(systemName: "textformat.size.larger") }
                    .help("Aumentar texto")
                Spacer()
                Button {
                    NSWorkspace.shared.open(url)
                } label: {
                    Image(systemName: "safari")
                }
                .help("Abrir en el navegador")
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .padding(8)

            if model.loading {
                ProgressView(value: model.progress)
                    .progressViewStyle(.linear)
            }

            NewsWebView(model: model)
        }
        .onChange(of: url) { _, newURL in model.load(newURL) }
    }
}

private struct NewsWebView: NSViewRepresentable {
    @ObservedObject var model: NewsReaderModel

    func makeNSView(context: Context) -> WKWebView {
        model.webView
    }

    func updateNSView(_ view: WKWebView, context: Context) {}
}

@MainActor
final class NewsReaderModel: NSObject, ObservableObject, WKNavigationDelegate {
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false
    @Published private(set) var loading = false
    @Published private(set) var progress = 0.0

    let webView: WKWebView
    private var observations: [NSKeyValueObservation] = []

    init(url: URL) {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        webView = WKWebView(frame: .zero, configuration: configuration)
        super.init()
        webView.navigationDelegate = self
        webView.setValue(true, forKey: "drawsBackground")
        webView.underPageBackgroundColor = .white
        webView.appearance = NSAppearance(named: .aqua)
        observeState()
        load(url)
    }

    func load(_ url: URL) {
        guard webView.url != url else { return }
        webView.load(URLRequest(url: url))
    }

    func goBack() { if webView.canGoBack { webView.goBack() } }
    func goForward() { if webView.canGoForward { webView.goForward() } }
    func reload() { webView.reload() }
    func increaseText() { webView.pageZoom = min(1.8, webView.pageZoom + 0.1) }
    func decreaseText() { webView.pageZoom = max(0.7, webView.pageZoom - 0.1) }

    private func observeState() {
        observations = [
            webView.observe(\.canGoBack, options: [.initial, .new]) { [weak self] view, _ in
                Task { @MainActor in self?.canGoBack = view.canGoBack }
            },
            webView.observe(\.canGoForward, options: [.initial, .new]) { [weak self] view, _ in
                Task { @MainActor in self?.canGoForward = view.canGoForward }
            },
            webView.observe(\.isLoading, options: [.initial, .new]) { [weak self] view, _ in
                Task { @MainActor in self?.loading = view.isLoading }
            },
            webView.observe(\.estimatedProgress, options: [.initial, .new]) { [weak self] view, _ in
                Task { @MainActor in self?.progress = view.estimatedProgress }
            },
        ]
    }
}

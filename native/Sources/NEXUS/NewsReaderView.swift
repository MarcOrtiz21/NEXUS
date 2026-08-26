import SwiftUI
import WebKit
import AppKit

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
                NexusToolbarButton(systemImage: "chevron.left", label: "Atrás", disabled: !model.canGoBack) { model.goBack() }
                NexusToolbarButton(systemImage: "chevron.right", label: "Adelante", disabled: !model.canGoForward) { model.goForward() }
                NexusToolbarButton(systemImage: "arrow.clockwise", label: "Recargar artículo") { model.reload() }
                Divider().frame(height: 16)
                NexusToolbarButton(systemImage: "textformat.size.smaller", label: "Reducir texto") { model.decreaseText() }
                NexusToolbarButton(systemImage: "textformat.size.larger", label: "Aumentar texto") { model.increaseText() }
                NexusToolbarButton(
                    systemImage: model.cookieShieldEnabled ? "checkmark.shield.fill" : "checkmark.shield",
                    label: model.cookieShieldEnabled ? "Mostrar avisos de cookies" : "Ocultar avisos de cookies",
                    helpText: model.cookieShieldEnabled
                        ? "Avisos de cookies ocultos. Clic para mostrarlos."
                        : "Mostrar avisos de cookies. Clic para ocultarlos."
                ) {
                    model.toggleCookieShield()
                }
                Spacer()
                NexusToolbarButton(systemImage: "safari", label: "Abrir en el navegador") {
                    NSWorkspace.shared.open(url)
                }
            }
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
    @Published private(set) var cookieShieldEnabled = NewsCookieShield.isEnabled

    let webView: WKWebView
    private var observations: [NSKeyValueObservation] = []

    init(url: URL) {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        if NewsCookieShield.isEnabled {
            NewsCookieShield.installUserScript(on: configuration.userContentController)
        }
        webView = WKWebView(frame: .zero, configuration: configuration)
        super.init()
        webView.navigationDelegate = self
        webView.setValue(true, forKey: "drawsBackground")
        webView.underPageBackgroundColor = .white
        webView.appearance = NSAppearance(named: .aqua)
        observeState()
        NewsCookieShield.clearLegacyRules(from: webView.configuration.userContentController)
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

    func toggleCookieShield() {
        cookieShieldEnabled.toggle()
        NewsCookieShield.isEnabled = cookieShieldEnabled
        let controller = webView.configuration.userContentController
        controller.removeAllUserScripts()
        NewsCookieShield.clearLegacyRules(from: controller)
        if cookieShieldEnabled {
            NewsCookieShield.installUserScript(on: controller)
        }
        webView.reload()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard cookieShieldEnabled else { return }
        webView.evaluateJavaScript(NewsCookieShield.userScript, completionHandler: nil)
    }

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

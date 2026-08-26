import AppKit
import SwiftUI

/// Configura una ventana opaca para que ningún panel dependa del escritorio
/// que haya detrás de la aplicación.
struct WindowConfigurator: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        WindowConfigurationView()
    }

    func updateNSView(_ view: NSView, context: Context) {
        configure(window: view.window)
    }

    private func configure(window: NSWindow?) {
        guard let window else { return }
        window.isOpaque = true
        window.backgroundColor = NSColor(
            calibratedRed: 0.08,
            green: 0.08,
            blue: 0.09,
            alpha: 1
        )
        window.titlebarAppearsTransparent = true
        window.styleMask.insert(.fullSizeContentView)
        window.toolbarStyle = .unified
        window.titleVisibility = .hidden
        window.titlebarSeparatorStyle = .none
    }
}

private final class WindowConfigurationView: NSView {
    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        guard let window else { return }
        window.isOpaque = true
        window.backgroundColor = NSColor(
            calibratedRed: 0.08,
            green: 0.08,
            blue: 0.09,
            alpha: 1
        )
        window.titlebarAppearsTransparent = true
        window.styleMask.insert(.fullSizeContentView)
        window.toolbarStyle = .unified
        window.titleVisibility = .hidden
        window.titlebarSeparatorStyle = .none
    }
}

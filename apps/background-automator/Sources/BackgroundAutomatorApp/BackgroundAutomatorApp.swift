import AppKit
import SwiftUI

@main
struct BackgroundAutomatorApp: App {
    @StateObject private var model = AppModel()

    init() {
        NSApplication.shared.setActivationPolicy(.accessory)
    }

    var body: some Scene {
        MenuBarExtra(
            "Background Automator",
            systemImage: "cursorarrow.click.2"
        ) {
            MenuContentView(model: model)
        }
        .menuBarExtraStyle(.window)
    }
}

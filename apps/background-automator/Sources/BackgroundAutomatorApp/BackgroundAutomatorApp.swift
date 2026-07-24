import AppKit
import BackgroundAutomatorRuntime
import SwiftUI

@main
struct BackgroundAutomatorApp: App {
    @StateObject private var model: AppModel

    init() {
        NSApplication.shared.setActivationPolicy(.accessory)
        let model = AppModel()
        _model = StateObject(wrappedValue: model)
        if AutomationLaunchOptions.shouldStartOnLaunch(
            arguments: ProcessInfo.processInfo.arguments
        ) {
            Task { @MainActor in
                model.toggleAutomation()
            }
        }
    }

    var body: some Scene {
        MenuBarExtra {
            MenuContentView(model: model)
        } label: {
            Image(systemName: model.status.symbolName)
                .accessibilityLabel(
                    "Background Automator: "
                        + model.status.koreanDescription
                )
        }
        .menuBarExtraStyle(.window)
    }
}

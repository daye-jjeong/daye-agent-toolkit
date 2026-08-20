import AppKit
import MAgentRuntime
import SwiftUI

@main
struct MAgentApp: App {
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
                    "m-agent: "
                        + model.status.koreanDescription
                )
        }
        .menuBarExtraStyle(.window)
    }
}

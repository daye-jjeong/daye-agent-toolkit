import AppKit
import SwiftUI

@main
struct BackgroundAutomatorApp: App {
    var body: some Scene {
        MenuBarExtra(
            "Background Automator",
            systemImage: "cursorarrow.click.2"
        ) {
            Text("준비 중")
            Divider()
            Button("종료") {
                NSApplication.shared.terminate(nil)
            }
        }
    }
}

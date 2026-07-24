import AppKit
import SwiftUI

struct MenuContentView: View {
    @ObservedObject var model: AppModel

    private static let actionDateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "ko_KR")
        formatter.dateFormat = "MM-dd HH:mm:ss"
        return formatter
    }()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Background Automator")
                .font(.headline)

            LabeledContent("상태") {
                Text(model.status.koreanDescription)
                    .multilineTextAlignment(.trailing)
            }

            Divider()

            Text("대상 앱 설정")
                .font(.subheadline)
                .fontWeight(.semibold)
            TextField(
                "번들 ID (필수)",
                text: $model.bundleIdentifier
            )
                .textFieldStyle(.roundedBorder)
                .disabled(model.areTargetFieldsLocked)
            TextField(
                "정확한 창 제목 (필수)",
                text: $model.titleContains
            )
                .textFieldStyle(.roundedBorder)
                .disabled(model.areTargetFieldsLocked)

            Button(model.primaryActionTitle) {
                model.toggleAutomation()
            }
            .keyboardShortcut(.defaultAction)
            .disabled(model.isTransitioning)

            if model.canRequestPermission {
                Button("시스템 권한 요청") {
                    model.requestMissingPermission()
                }
                .disabled(model.isTransitioning)
            }

            Divider()

            LabeledContent("마지막 동작") {
                VStack(alignment: .trailing, spacing: 2) {
                    Text(model.lastActionDescription)
                    if let timestamp = model.lastActionAt {
                        Text(
                            Self.actionDateFormatter.string(
                                from: timestamp
                            )
                        )
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                }
            }

            LabeledContent("완료한 던전") {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(model.activitySummary.dungeonRuns)회")
                    if let topDungeon = model.topDungeonSummary {
                        Text(topDungeon)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Button("진단 폴더 열기") {
                model.openDiagnosticsFolder()
            }

            Divider()

            Button("종료") {
                model.quit()
            }
        }
        .padding(14)
        .frame(width: 360)
    }
}

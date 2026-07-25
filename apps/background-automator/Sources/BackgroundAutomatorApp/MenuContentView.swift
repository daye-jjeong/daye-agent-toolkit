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

            if model.status == .pausedRestorationFailure {
                Button("복원 실패에서 재개") {
                    model.resumeAfterRestorationFailure()
                }
                .disabled(model.isTransitioning)
            }

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

            // 클릭이 아니라 결과 화면 등장으로 세기 때문에, 사용자가 직접
            // 넘긴 판도 포함된다(위 '완료한 던전'은 앱이 누른 것만 센다).
            LabeledContent("기록된 사이클") {
                Text("\(model.cycleSummary.totalCycles)회")
            }

            Toggle("은동전 쓰기 (전리품 2배)", isOn: $model.usesSilverCoin)
                .disabled(model.isRunning || model.isTransitioning)
            Text(
                model.usesSilverCoin
                    ? "임무를 그대로 두고 입장합니다. 한 판에 은동전 10개."
                    : "임무를 해제하고 입장합니다. 은동전을 쓰지 않습니다."
            )
            .font(.caption)
            .foregroundStyle(.secondary)

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

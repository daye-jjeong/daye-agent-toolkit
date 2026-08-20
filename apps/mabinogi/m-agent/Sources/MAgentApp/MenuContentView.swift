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
            Text("m-agent")
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
            LabeledContent("오늘 사이클") {
                VStack(alignment: .trailing, spacing: 2) {
                    // 돌린 시간은 자리를 비운 공백을 빼고 센다. '가동 시간'은
                    // 이번에 시작한 뒤부터라 껐다 켜면 0으로 돌아간다.
                    if let active = model.cycleSummary.todayActiveDescription {
                        Text("\(model.cycleSummary.todayCycles)회 · \(active)")
                    } else {
                        Text("\(model.cycleSummary.todayCycles)회")
                    }
                    Text("누적 \(model.cycleSummary.totalCycles)회")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            if let uptime = model.uptimeDescription {
                LabeledContent("가동 시간") {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(uptime)
                        if let rate = model.cycleRateDescription {
                            Text(rate)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }

            // '전리품 2배'는 이 토글이 아니라 아래 '더블 루팅(도전)'의
            // 문구다. 임무 선택은 보상을 받느냐 마느냐다.
            Toggle("은동전 쓰기 (임무 보상 받기)", isOn: $model.usesSilverCoin)
                .disabled(model.isRunning || model.isTransitioning)
            Text(
                model.usesSilverCoin
                    ? "임무를 그대로 두고 입장해 임무 보상을 받습니다. 한 판에 은동전 10개."
                    : "임무를 해제하고 입장합니다. 은동전도 임무 보상도 없습니다."
            )
            .font(.caption)
            .foregroundStyle(.secondary)

            // 공물 던전(페카 고분)은 더블 루팅이 없어 은동전 규칙이 못 잡는다.
            Toggle("공물 쓰기 (임무 보상 받기)", isOn: $model.usesTribute)
                .disabled(model.isRunning || model.isTransitioning)
            Text(
                model.usesTribute
                    ? "임무를 그대로 두고 입장해 임무 보상을 받습니다. 한 판에 공물 1개."
                    : "임무를 해제하고 입장합니다. 공물도 임무 보상도 없습니다."
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

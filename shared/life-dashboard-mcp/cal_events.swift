#!/usr/bin/env swift
// cal_events.swift — Extract calendar events via EventKit.
// Usage: swift cal_events.swift --from 2026-03-07 --to 2026-03-08
// Output: pipe-delimited lines: calendar|title|start|end|allDay

import EventKit
import Foundation

// MARK: - Config

let allowedCalendars: Set<String> = [
    "개인", "업무", "건강", "학습", "daye@ronik.io"
]

// MARK: - Args

func parseArgs() -> (from: Date, to: Date) {
    let args = CommandLine.arguments
    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd"
    df.timeZone = TimeZone(identifier: "Asia/Seoul")

    var fromStr = ""
    var toStr = ""
    var i = 1
    while i < args.count {
        if args[i] == "--from" && i + 1 < args.count {
            fromStr = args[i + 1]; i += 2
        } else if args[i] == "--to" && i + 1 < args.count {
            toStr = args[i + 1]; i += 2
        } else {
            i += 1
        }
    }

    guard let from = df.date(from: fromStr), let to = df.date(from: toStr) else {
        fputs("Usage: swift cal_events.swift --from YYYY-MM-DD --to YYYY-MM-DD\n", stderr)
        exit(1)
    }
    return (from, to)
}

// MARK: - Main

let (fromDate, toDate) = parseArgs()

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)

store.requestFullAccessToEvents { granted, error in
    guard granted else {
        fputs("ERROR: Calendar access denied\n", stderr)
        exit(2)
    }

    let predicate = store.predicateForEvents(withStart: fromDate, end: toDate, calendars: nil)
    let events = store.events(matching: predicate)

    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd HH:mm"
    df.timeZone = TimeZone(identifier: "Asia/Seoul")

    for event in events {
        let calName = event.calendar.title
        guard allowedCalendars.contains(calName) else { continue }
        guard !event.isAllDay else { continue }

        let title = (event.title ?? "").replacingOccurrences(of: "|", with: "/")
        let s = df.string(from: event.startDate)
        let e = df.string(from: event.endDate)
        print("\(calName)|\(title)|\(s)|\(e)")
    }

    semaphore.signal()
}

semaphore.wait()

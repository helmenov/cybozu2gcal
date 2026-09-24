import csv
import datetime

def read_event_list_from_cybozu_csv(cybozu_csv_path : str) -> list:
    """
    サイボウズ Office 出力のカレンダーCSVデータからイベントデータを読む

    Parameters
    ----------
    cybozu_csv_path : str
        CSV path

    Returns
    -------
    cybozu_event_list : list
        イベントリスト
    """

    with open(cybozu_csv_path, encoding="utf-8_sig") as f:
        reader = csv.reader(f)
        csv_data = [row for row in reader]

    cybozu_event_list = []
    for row in csv_data:
        # header行はスキップ
        if row[0] == "開始日付":
            continue
        event = {
#            'event_id': row[0],
            'start_date': row[0],
            'start_time': row[1],
            'end_date': row[2],
            'end_time': row[3],
            'subject_type': row[4],
            'subject_title': row[5],
            'memo': row[6],
            'attendee': row[7],
            'facility': row[8],
        }
        cybozu_event_list.append(event)

    return cybozu_event_list

def convert_event_list_from_cybozu_to_gcal(cybozu_event_list : list) -> list:
    """
    サイボウズのイベントデータをGoogle Calendar用のデータに変換する

    Parameters
    ----------
    cybozu_event_list : list
        サイボウズのイベントデータ

    Returns
    -------
    gcal_event_list : list
        Google Calendar用のイベントリスト（2次元配列）
    """

    gcal_event_list = []

    header = ["Subject",
              "Start Date",
              "Start Time",
              "End Date",
              "End Time",
              "All Day Event",
              "Description"]
    gcal_event_list.append(header)

    for cy_event in cybozu_event_list:
        # 予定名：
        # 予定ラベル（「出張」「会議」など）があれば付加
        subject = cy_event['subject_title']
        if cy_event['subject_type']:
            subject = cy_event['subject_type'] + ":" + subject

        # 開始日時
        start_date = cy_event['start_date']
        start_time = cy_event['start_time']

        # 終了日時
        end_date = cy_event['end_date']
        end_time = cy_event['end_time']

        # 終日予定の判定：
        # 開始時刻・終了時刻がともに空白のとき終日予定とする
        is_all_day = not cy_event['start_time'] and not cy_event['end_time']
        all_day_flag = "True" if is_all_day else "False"

        # 終日の期間予定の判定：
        # Google calendarでは、終了時間のない期間予定は
        # 実際の期間終了日の翌日をend_dateに設定する必要がある
        is_multi_day = all_day_flag \
                       and (start_date != end_date) \
                       and (end_time == "")
        if is_multi_day:
            d = datetime.datetime.strptime(end_date, '%Y/%m/%d')
            d += datetime.timedelta(days = 1)
            end_date = d.strftime('%Y/%m/%d')

        # 説明
        description = cy_event['memo']

        gcal_event = [
            subject,
            start_date,
            start_time,
            end_date,
            end_time,
            all_day_flag,
            description,
        ]
        gcal_event_list.append(gcal_event)

    return gcal_event_list

def write_event_list_as_gcal_csv(gcal_csv_path : str, gcal_event_list : list):
    """
    Google Calendar用のイベントデータをCSVに書き込む

    Parameters
    ----------
    gcal_csv_path : str
        Google calendar用のCSV保存先データパス
    gcal_event_list : list
        Google calendar用のイベントデータ
    """

    with open(gcal_csv_path, 'w', encoding="utf-8_sig", newline='') as f:
        writer = csv.writer(f)
        writer.writerows(gcal_event_list)

def convert_event_list_from_cybozu_to_ical(cybozu_event_list : list, ics_file_path : str):
    """
    サイボウズのイベントデータをiCalendar用のデータに変換する

    Parameters
    ----------
    cybozu_event_list : list
        サイボウズのイベントデータ
    ics_file_path : str
        生成するiCalendarファイルのパス

    Returns
    -------
    None
    """

    # icsファイルを作成するためのライブラリをインポート
    from icalendar import Calendar, Event
    cal = Calendar()
    tz = datetime.timezone(datetime.timedelta(hours=9))  # JST
    for cy_event in cybozu_event_list:
        event = Event()
        # 予定名：
        # 予定ラベル（「出張」「会議」など）があれば付加
        subject = cy_event['subject_title']
        if cy_event['subject_type']:
            subject = cy_event['subject_type'] + ":" + subject
        event.add('summary', subject)

        # 開始日時
        start_date = cy_event['start_date']
        start_time = cy_event['start_time']

        # 終了日時
        end_date = cy_event['end_date']
        end_time = cy_event['end_time']

        # 終日予定の判定：
        # 開始時刻・終了時刻がともに空白のとき終日予定とする
        is_all_day = not cy_event['start_time'] and not cy_event['end_time']

        if is_all_day:
            dt_start = datetime.datetime.strptime(start_date, '%Y/%m/%d').date()
            dt_end = datetime.datetime.strptime(end_date, '%Y/%m/%d').date() + datetime.timedelta(days=1)  # iCalendarでは終了日を含まないため、1日加算する
            event.add('dtstart;VALUE=DATE', dt_start)
            event.add('dtend;VALUE=DATE', dt_end)
        else:
            if not cy_event['end_time']:
                # 終了時刻が空白の場合は、開始時刻の1時間後を終了時刻とする
                start_dt = datetime.datetime.strptime(f"{start_date} {start_time}", '%Y/%m/%d %H:%M:%S')
                end_dt = start_dt + datetime.timedelta(hours=1)
                end_date = end_dt.strftime('%Y/%m/%d')
                end_time = end_dt.strftime('%H:%M:%S')
            dt_start = datetime.datetime.strptime(f"{start_date} {start_time}", '%Y/%m/%d %H:%M:%S')
            dt_end = datetime.datetime.strptime(f"{end_date} {end_time}", '%Y/%m/%d %H:%M:%S')
            event.add('dtstart', dt_start)
            event.add('dtend', dt_end)

        # 説明
        description = cy_event['memo']
        # descriptionを追加する際に、改行コードをCRLFに変換する
        #description = description.replace('\r\n', '\\n').replace('\n', '\\n')
        event.add('description', description)

        location = cy_event['facility']
        event.add('location', location)

        cal.add_component(event)

    cal.add('prodid', '-//Kotaro Sonoda//Product//EN')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', 'Cybozu Calendar')
    cal.add('X-WR-TIMEZONE', 'Asia/Tokyo')
    cal.add('X-WR-CALDESC', 'Imported from Cybozu Calendar')

    # icsファイルに書き込む
    with open(ics_file_path, 'wb') as f:
        f.write(cal.to_ical())

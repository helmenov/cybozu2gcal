import os
from dotenv import load_dotenv
load_dotenv()  # .env ファイルの内容を環境変数に読み込む
from playwright.sync_api import sync_playwright
import argparse
from cybozu2gcal.lib import convert_event_list_from_cybozu_to_gcal, convert_event_list_from_cybozu_to_ical, read_event_list_from_cybozu_csv, write_event_list_as_gcal_csv
import time

CYBOSE_URL = os.environ["CYBOSE_URL"]
CYBOSE_ORG = os.environ["CYBOSE_ORG"]
CYBOSE_USER = os.environ["CYBOSE_USER"]
CYBOSE_PASSWORD = os.environ["CYBOSE_PASSWORD"]

def parse_args():
    print('Login to Cybozu Office...')
    parser = argparse.ArgumentParser(description="サイボウズOffice ログイン")
    parser.add_argument(
        "--mode",
        choices=["personal", "viewer"],
        default="personal",
        help="personal: 個人スケジュール登録用ログイン / viewer: 閲覧ユーザログイン",
    )
    return parser.parse_args()

def login_personal(page):
    page.goto(CYBOSE_URL)

    # 1. 「切り替える」
    #page.get_by_role("button", name="切り替える").click()
    page.click("a:has-text('切り替える')")

    # 2. 組織を選んで切り替える
    #page.get_by_label("組織").select_option(label=CYBOSE_ORG)
    page.select_option("select[name='Group']", "5551")
    #page.get_by_role("button", name="切り替える").click()
    page.click("input[name='Submit']")

    # 3. 名前を選び、パスワードを入力してログイン
    #page.get_by_label("名前").select_option(label=CYBOSE_USER)
    page.select_option("select[name='_ID']", "15697")
    #page.get_by_label("パスワード").fill(CYBOSE_PASSWORD)
    page.fill("input[name='Password']", CYBOSE_PASSWORD)
    #page.get_by_role("button", name="ログイン").click()
    page.click("input[name='Submit'][type='submit']")

    ics_path = export_schedule_csv(page)  # CSV書き出しのテスト

    # 4. ログイン完了の検証(実際に表示される文言/要素に置き換える)
    logout(page)

    return ics_path

def login_viewer(page):
    page.goto(CYBOSE_URL)
    #page.get_by_role("button", name="閲覧ユーザとしてログイン").click()
    page.click("input[name='guestUser']")
    ics_path = export_schedule_csv(page)  # CSV書き出しのテスト

    logout(page)

    return ics_path

def select_extreme_option(page, selector, pick="min"):
    """
    select 要素の option の value(数値文字列)一覧を実行時に DOM から取得し，
    最小値または最大値を選択状態にする．
    サイボウズ側で選択可能な範囲(年・月・日の上限/下限)を実行時に読み取るため，
    事前にその範囲を決め打ちする必要がない．
    """
    time.sleep(1)  # ページ遷移の待機
    values = page.locator(f"{selector} option").evaluate_all(
        "options => options.map(o => o.value)"
    )
    if pick == "min":
        target = min(values, key=int)
    elif pick == "max":
        target = max(values, key=int)
    else:
        target = str(pick)  # 数値文字列を指定した場合はその値を選択する
    page.select_option(selector, target)
    return target


def select_widest_period(page):
    """
    期間指定の開始日は選択可能な最も古い日付，終了日は選択可能な最も新しい日付を選び，
    取得できる期間を最長にする．
    """
    select_extreme_option(page, "select[name='SetDate.Year']", pick="2026")
    select_extreme_option(page, "select[name='SetDate.Month']", pick="6")
    select_extreme_option(page, "select[name='SetDate.Day']", pick="1")
    select_extreme_option(page, "select[name='EndDate.Year']", pick="max")
    select_extreme_option(page, "select[name='EndDate.Month']", pick="max")
    select_extreme_option(page, "select[name='EndDate.Day']", pick="max")


def export_schedule_csv(page, save_dir="."):
    print('Export schedule from csv to ical')
    # 個人設定 → 詳細設定タブ
    time.sleep(1)  # ページ遷移の待機
    page.locator("#header-menu-user").get_by_role("link").first.click()
    page.get_by_role("link", name="個人設定").click()
    page.get_by_role("cell", name="詳細設定").click()

    # スケジュールと施設予約 → CSVファイルへの書き出し
    page.get_by_role("link", name="スケジュール と施設予約").click()
    page.get_by_role("link", name="CSVファイルへの 書き出し").click()

    # 期間を可能な最長範囲にする
    # 開始日は選択肢の中で最も古い日付，終了日は選択肢の中で最も新しい日付を選ぶ
    select_widest_period(page)

    # 期間の現在値を読み取る(ファイル名生成用)
    start_year = page.locator("select[name='SetDate.Year']").input_value()
    start_month = page.locator("select[name='SetDate.Month']").input_value()
    start_day = page.locator("select[name='SetDate.Day']").input_value()
    end_year = page.locator("select[name='EndDate.Year']").input_value()
    end_month = page.locator("select[name='EndDate.Month']").input_value()
    end_day = page.locator("select[name='EndDate.Day']").input_value()

    period = (
        f"{start_year}{start_month.zfill(2)}{start_day.zfill(2)}"
        f"-{end_year}{end_month.zfill(2)}{end_day.zfill(2)}"
    )

    # 文字コードを選んで書き出す
    page.locator("select[name='oencoding']").select_option("UTF-8;BOM")
    # ダウンロードの待機と書き出しボタンのクリック
    # 待機時間を長めに設定しておくと，ダウンロードが完了する前に次の処理に進んでしまうことを防げる
    page.set_default_timeout(60000)  # 60秒
    with page.expect_download() as download_info:
        page.get_by_role("button", name="書き出す").click()
    download = download_info.value

    save_path = os.path.join(save_dir, f"cybozu.csv")
    download.save_as(save_path)

    cybozu_events = read_event_list_from_cybozu_csv(save_path)

    #gcal_events = convert_event_list_from_cybozu_to_gcal(cybozu_events)
    #gcal_path = os.path.join(save_dir, f"gcal_{period}.csv")
    #write_event_list_as_gcal_csv(gcal_path, gcal_events)

    ics_path = os.path.join(save_dir, f"cybozu.ics")
    convert_event_list_from_cybozu_to_ical(cybozu_events, ics_path)

    return ics_path


def logout(page):
    page.locator("#header-menu-user").get_by_role("link").first.click()
    page.get_by_role("link", name="ログアウト").click()

def main():
    args = parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if args.mode == "personal":
            ics_path = login_personal(page)
        else:
            ics_path = login_viewer(page)

        browser.close()

if __name__ == "__main__":
    main()



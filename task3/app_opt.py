import flet as ft
import requests
import sqlite3
from datetime import datetime


AREA_URL = "https://www.jma.go.jp/bosai/common/const/area.json"
FORECAST_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/{}.json"
ICON_URL_BASE = "https://www.jma.go.jp/bosai/forecast/img/{}.png" # 気象のアイコンを確実に表示するためのサイト
DB_NAME = "weather_base.db"


# データベース設定
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS areas 
                   (area_code TEXT PRIMARY KEY, area_name TEXT, center_name TEXT, is_favorite INTEGER DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS forecasts 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, area_code TEXT, forecast_date TEXT, 
                    weather_text TEXT, weather_code TEXT, UNIQUE(area_code, forecast_date))''')
    conn.commit()
    conn.close()

def sync_areas_to_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM areas")
    if cur.fetchone()[0] == 0:
        res = requests.get(AREA_URL).json()
        offices, centers = res.get("offices", {}), res.get("centers", {})
        for code, info in offices.items():
            parent_name = centers.get(info["parent"], {}).get("name", "その他")
            cur.execute("INSERT INTO areas (area_code, area_name, center_name) VALUES (?, ?, ?)",
                        (code, info["name"], parent_name))
        conn.commit()
    conn.close()


# アプリ本体
def main(page: ft.Page):
    init_db()
    sync_areas_to_db()
    page.title = "改良版天気予報アプリ"
    page.theme_mode = ft.ThemeMode.LIGHT
    
    # 状態管理
    state = {
        "current_area_code": None,
        "search_query": "",
        "selected_nav_index": 0
    }

    forecast_display = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE)
    sidebar_column = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True)

    # 天気予報の取得、データベース保存
    def get_weather(area_code, area_name):
        state["current_area_code"] = area_code
        try:
            forecast_display.controls.clear()
            forecast_display.controls.append(ft.ProgressBar())
            page.update()

            res = requests.get(FORECAST_URL.format(area_code)).json()
            time_series = res[0]["timeSeries"][0]
            dates = time_series["timeDefines"]
            area_data = time_series["areas"][0]
            weathers = area_data["weathers"]
            codes = area_data["weatherCodes"]

            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            forecast_list = []
            for i in range(len(weathers)):
                date_str = dates[i][:10]
                cur.execute("""INSERT OR REPLACE INTO forecasts 
                               (area_code, forecast_date, weather_text, weather_code) 
                               VALUES (?, ?, ?, ?)""", (area_code, date_str, weathers[i], codes[i]))
                forecast_list.append({"date": date_str, "text": weathers[i], "code": codes[i]})
            conn.commit()
            cur.execute("SELECT is_favorite FROM areas WHERE area_code = ?", (area_code,))
            is_fav = cur.fetchone()[0]
            conn.close()

            show_forecast_ui(area_name, forecast_list, is_fav)
        except Exception as e:
            forecast_display.controls.append(ft.Text(f"エラー: {e}", color="red"))
            page.update()

    # 天気予報のUI表示
    def show_forecast_ui(name, forecast_list, is_fav):
        fav_icon = ft.Icons.STAR if is_fav else ft.Icons.STAR_BORDER
        fav_color = ft.Colors.AMBER if is_fav else ft.Colors.GREY_400

        forecast_display.controls.clear()
        forecast_display.controls.append(
            ft.Row([
                ft.Text(f"{name}の3日間の予報", style=ft.TextThemeStyle.HEADLINE_SMALL, weight="bold"),
                ft.IconButton(icon=fav_icon, icon_color=fav_color, 
                             on_click=lambda _: on_fav_click(state["current_area_code"], is_fav, name, forecast_list))
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

        cards_row = ft.Row(spacing=20, scroll=ft.ScrollMode.ADAPTIVE)
        for item in forecast_list:
            str_code = str(item["code"])[:3]
            main_url = ICON_URL_BASE.format(str_code)
            backup_url = ICON_URL_BASE.format(str_code[0] + "00")
            display_date = datetime.strptime(item["date"], "%Y-%m-%d").strftime("%m/%d")

            cards_row.controls.append(
                ft.Card(content=ft.Container(padding=20, width=180, content=ft.Column([
                    ft.Text(display_date, size=18, weight="bold"),
                    ft.Image(src=main_url, width=64, height=64,
                            error_content=ft.Image(src=backup_url, width=64, 
                            error_content=ft.Icon(ft.Icons.WB_CLOUDY_OUTLINED, size=40))),
                    ft.Text(item["text"], size=14, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)))
            )
        forecast_display.controls.append(cards_row)
        page.update()


    # ユーザーのお気に入り登録、解除処理
    def on_fav_click(code, current_status, name, forecast_list):
        new_status = 1 if current_status == 0 else 0
        conn = sqlite3.connect(DB_NAME); cur = conn.cursor()
        cur.execute("UPDATE areas SET is_favorite = ? WHERE area_code = ?", (new_status, code)); conn.commit(); conn.close()
        show_forecast_ui(name, forecast_list, new_status)
        build_sidebar()

    # サイドバー
    def build_sidebar():
        sidebar_column.controls.clear()
        conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; cur = conn.cursor()
        
        if state["selected_nav_index"] == 0:
            search_container.visible = True
            cur.execute("SELECT * FROM areas WHERE area_name LIKE ? ORDER BY is_favorite DESC, center_name ASC", (f"%{state['search_query']}%",))
            rows = cur.fetchall()
            current_center = ""
            exp_tile = None
            for row in rows:
                if row["center_name"] != current_center:
                    current_center = row["center_name"]
                    exp_tile = ft.ExpansionTile(title=ft.Text(current_center, weight="bold"), initially_expanded=bool(state["search_query"]))
                    sidebar_column.controls.append(exp_tile)
                fav_mark = "⭐ " if row["is_favorite"] else ""
                exp_tile.controls.append(ft.ListTile(title=ft.Text(f"{fav_mark}{row['area_name']}"), on_click=lambda e, r=row: get_weather(r["area_code"], r["area_name"])))
        else:
            search_container.visible = False
            cur.execute("SELECT * FROM areas WHERE is_favorite = 1 ORDER BY area_name ASC")
            rows = cur.fetchall()
            if not rows:
                sidebar_column.controls.append(ft.Container(padding=20, content=ft.Text("お気に入りはまだありません。\n星マークを押して登録してください。", color="grey")))
            for row in rows:
                sidebar_column.controls.append(
                    ft.ListTile(leading=ft.Icon(ft.Icons.STAR, color="amber"), title=ft.Text(row["area_name"]), on_click=lambda e, r=row: get_weather(r["area_code"], r["area_name"]))
                )
        conn.close()
        page.update()

    # クリックをされた時に上で設定した処理を行う
    def on_nav_change(e): 
        state["selected_nav_index"] = e.control.selected_index
        build_sidebar()

    def on_search_change(e):
        state["search_query"] = e.control.value
        build_sidebar()

    # UI構成部分
    # 地域検索を追加
    search_field = ft.TextField(label="地域検索", prefix_icon=ft.Icons.SEARCH, height=50, on_change=on_search_change)
    search_container = ft.Container(content=search_field, padding=ft.padding.only(bottom=10))

    nav_rail = ft.NavigationRail(
        selected_index=0, label_type=ft.NavigationRailLabelType.ALL, min_width=100,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.WB_SUNNY_OUTLINED, selected_icon=ft.Icons.WB_SUNNY, label="天気予報"),
            ft.NavigationRailDestination(icon=ft.Icons.STAR_BORDER, selected_icon=ft.Icons.STAR, label="お気に入り"),
        ],
        on_change=on_nav_change
    )

    build_sidebar()
    page.add(ft.Row([
        nav_rail,
        ft.VerticalDivider(width=1),
        ft.Container(width=280, padding=10, content=ft.Column([search_container, sidebar_column])),
        ft.VerticalDivider(width=1),
        ft.Container(expand=True, padding=20, content=forecast_display)
    ], expand=True))

ft.app(target=main)
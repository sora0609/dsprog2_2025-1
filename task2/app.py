import flet as ft
import requests


AREA_URL = "https://www.jma.go.jp/bosai/common/const/area.json"
FORECAST_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/{}.json"
ICON_URL_BASE = "https://www.jma.go.jp/bosai/forecast/img/{}.png" # 気象のアイコンを確実に表示するためのサイト

def main(page: ft.Page):
    page.title = "天気予報アプリ"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 1000
    page.window_height = 800

    forecast_display = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE)

    def get_weather(area_code, area_name):
        try:
            forecast_display.controls.clear()
            forecast_display.controls.append(ft.ProgressBar())
            page.update()

            response = requests.get(FORECAST_URL.format(area_code))
            data = response.json()
            
            report = data[0]
            time_series = report["timeSeries"][0]
            
            forecast_display.controls.clear()
            forecast_display.controls.append(
                ft.Text(f"{area_name}の予報", style=ft.TextThemeStyle.HEADLINE_SMALL, weight=ft.FontWeight.BOLD)
            )

            for area_info in time_series["areas"]:
                sub_area_name = area_info["area"]["name"]
                weather_text = area_info["weathers"][0]
                
                raw_code = area_info["weatherCodes"][0]
                code = str(raw_code)[:3] # 頭文字3つをとる
                
                # 気象庁のサーバーの画像番号にマッピングさせる
                main_digit = code[0]
                icon_url = ICON_URL_BASE.format(code)
                
                # もし画像がなかったら100,200...を代わりに出す
                backup_url = ICON_URL_BASE.format(main_digit + "00")

                forecast_display.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=10,
                            content=ft.ListTile(
                                leading=ft.Image(
                                    src=icon_url,
                                    width=50,
                                    height=50,
                                    error_content=ft.Image(src=backup_url, width=50, height=50) 
                                ),
                                title=ft.Text(sub_area_name, weight=ft.FontWeight.BOLD),
                                subtitle=ft.Text(weather_text),
                            )
                        )
                    )
                )
            page.update()
        except Exception as e:
            forecast_display.controls.clear()
            forecast_display.controls.append(ft.Text(f"エラー: {e}", color=ft.Colors.RED))
            page.update()

   
    # 地域選択を行うバー
    sidebar_items = []
    try:
        area_res = requests.get(AREA_URL).json()
        centers = area_res.get("centers", {})
        offices = area_res.get("offices", {})

        for c_code, c_info in centers.items():
            children = []
            for o_code, o_info in offices.items():
                if o_info["parent"] == c_code:
                    children.append(
                        ft.ListTile(
                            title=ft.Text(o_info["name"]),
                            on_click=lambda e, code=o_code, name=o_info["name"]: get_weather(code, name)
                        )
                    )
            sidebar_items.append(
                ft.ExpansionTile(
                    title=ft.Text(c_info["name"]),
                    leading=ft.Icon(ft.Icons.LOCATION_ON),
                    controls=children
                )
            )
    except Exception as e:
        sidebar_items.append(ft.Text("地域情報の取得失敗"))

    page.add(
        ft.Row(
            [
                ft.NavigationRail(
                    selected_index=0,
                    label_type=ft.NavigationRailLabelType.ALL,
                    destinations=[
                        ft.NavigationRailDestination(icon=ft.Icons.CLOUD, label="天気予報"),
                    ],
                ),
                ft.VerticalDivider(width=1),
                ft.Container(
                    width=250,
                    content=ft.Column(sidebar_items, scroll=ft.ScrollMode.ALWAYS)
                ),
                ft.VerticalDivider(width=1),
                ft.Container(
                    expand=True,
                    padding=20,
                    content=forecast_display
                )
            ],
            expand=True
        )
    )

ft.app(target=main)
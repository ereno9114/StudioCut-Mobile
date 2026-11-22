import os
import re
import time
import random
import shutil
import tempfile
import subprocess
import threading
import flet as ft


def ffmpeg_komut_calistir(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def video_suresi_al(video_yolu):
    res = ffmpeg_komut_calistir(["ffmpeg", "-i", video_yolu])
    eslesme = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if eslesme:
        saat, dk, sn = float(eslesme.group(1)), float(eslesme.group(2)), float(eslesme.group(3))
        return saat * 3600 + dk * 60 + sn
    return 10.0


def ses_var_mi(video_yolu):
    res = ffmpeg_komut_calistir(["ffmpeg", "-i", video_yolu])
    return "Audio:" in res.stderr


def main(page: ft.Page):
    page.title = "STUDIO CUT Mobile"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0d1117"
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO

    secili_videolar = []
    secili_muzik = {"yol": ""}
    son_cikti = {"yol": ""}

    txt_video_durum = ft.Text("Henüz video seçilmedi", color="#8b949e", size=12)
    txt_muzik_durum = ft.Text("Müzik seçilmedi (İsteğe bağlı)", color="#8b949e", size=12)
    txt_log = ft.Text("Hazır. Videolarınızı seçip kurguyu başlatın.", color="#c9d1d9", size=12)
    progress_bar = ft.ProgressBar(value=0, color="#2f81f7", bgcolor="#161b22", visible=False)

    dd_tarz = ft.Dropdown(
        label="Kurgu Tarzı",
        value="araba",
        border_color="#30363d",
        options=[
            ft.dropdown.Option("araba", "Araba / Aksiyon (Hızlı Ritim & Zoom)"),
            ft.dropdown.Option("vlog", "Vlog (Konuşma Koru & Boşluk At)"),
            ft.dropdown.Option("oyun", "Oyun / Maç Özeti (Aksiyon Kesimi)"),
            ft.dropdown.Option("manzara", "Sinematik Manzara (Akıcı Geçiş)"),
        ],
    )

    dd_oran = ft.Dropdown(
        label="Ekran Formatı",
        value="9:16",
        border_color="#30363d",
        options=[
            ft.dropdown.Option("9:16", "9:16 Dikey (Tam Ekran)"),
            ft.dropdown.Option("16:9", "16:9 Yatay"),
        ],
    )

    slider_siklik = ft.Slider(
        min=25, max=80, divisions=11, value=50,
        label="Kurgu Yoğunluğu: %{value}", active_color="#2f81f7"
    )

    txt_talimat = ft.TextField(
        label="Ekstra Kurgu Notu (İsteğe Bağlı)",
        hint_text="Örn: Bass vuruşlarında hızlı geçiş yap...",
        multiline=True,
        min_lines=2,
        max_lines=3,
        border_color="#30363d",
    )

    def video_secildi(e: ft.FilePickerResultEvent):
        if e.files:
            secili_videolar.clear()
            for f in e.files:
                if f.path:
                    secili_videolar.append(f.path)
            txt_video_durum.value = f"✔ {len(secili_videolar)} video seçildi"
            txt_video_durum.color = "#3fb950"
            page.update()

    def muzik_secildi(e: ft.FilePickerResultEvent):
        if e.files and e.files[0].path:
            secili_muzik["yol"] = e.files[0].path
            txt_muzik_durum.value = f"✔ Müzik: {os.path.basename(secili_muzik['yol'])[:28]}"
            txt_muzik_durum.color = "#58a6ff"
            page.update()

    video_picker = ft.FilePicker(on_result=video_secildi)
    muzik_picker = ft.FilePicker(on_result=muzik_secildi)
    page.overlay.extend([video_picker, muzik_picker])

    def kurguyu_isle():
        if not secili_videolar:
            txt_log.value = "⚠ Lütfen önce en az 1 video seçin!"
            page.update()
            return

        btn_baslat.disabled = True
        progress_bar.visible = True
        progress_bar.value = 0.1
        txt_log.value = "[1/3] Videolar analiz ediliyor..."
        page.update()

        gecici = tempfile.mkdtemp(prefix="studiocut_mob_")
        try:
            tarz = dd_tarz.value
            yatay = dd_oran.value == "16:9"
            w, h = (1280, 720) if yatay else (720, 1280)
            yogunluk = slider_siklik.value / 100.0

            parcalar = []
            rng = random.Random(int(time.time()))

            for v_idx, v_yol in enumerate(secili_videolar):
                sure = video_suresi_al(v_yol)
                ses_var = ses_var_mi(v_yol)

                if tarz in ("araba", "oyun"):
                    klip_uzunlugu = rng.uniform(0.9, 1.6)
                    adim = max(1.8, klip_uzunlugu / yogunluk)
                elif tarz == "manzara":
                    klip_uzunlugu = rng.uniform(2.5, 4.0)
                    adim = max(3.5, klip_uzunlugu / yogunluk)
                else:
                    klip_uzunlugu = rng.uniform(3.5, 6.0)
                    adim = max(5.0, klip_uzunlugu / yogunluk)

                t = 0.2
                p_sayac = 0
                while t + klip_uzunlugu < sure and p_sayac < 18:
                    out_p = os.path.join(gecici, f"p_{v_idx}_{p_sayac:02d}.mp4")

                    if tarz in ("araba", "oyun"):
                        vf = (
                            f"scale={int(w*1.08)}:{int(h*1.08)}:force_original_aspect_ratio=increase,"
                            f"crop={w}:{h},eq=contrast=1.15:saturation=1.12"
                        )
                    else:
                        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"

                    cmd = ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-t", f"{klip_uzunlugu:.2f}", "-i", v_yol]
                    if not ses_var:
                        cmd += ["-f", "lavfi", "-t", f"{klip_uzunlugu:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

                    cmd += [
                        "-vf", vf,
                        "-map", "0:v", "-map", "0:a" if ses_var else "1:a",
                        "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                        out_p,
                    ]
                    ffmpeg_komut_calistir(cmd)
                    if os.path.exists(out_p):
                        parcalar.append(out_p)
                    t += adim + rng.uniform(-0.3, 0.4)
                    p_sayac += 1

                progress_bar.value = 0.2 + 0.5 * ((v_idx + 1) / len(secili_videolar))
                txt_log.value = f"[2/3] {len(parcalar)} sahne kesildi, birleştiriliyor..."
                page.update()

            if not parcalar:
                raise RuntimeError("Sahneler kesilemedi.")

            liste_txt = os.path.join(gecici, "liste.txt")
            with open(liste_txt, "w", encoding="utf-8") as f:
                for p in parcalar:
                    f.write(f"file '{p}'\n")

            ham_video = os.path.join(gecici, "ham.mp4")
            ffmpeg_komut_calistir(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", liste_txt, "-c", "copy", ham_video])

            kayit_klasoru = "/storage/emulated/0/Download" if os.path.exists("/storage/emulated/0/Download") else os.path.expanduser("~")
            cikti_yolu = os.path.join(kayit_klasoru, f"StudioCut_{int(time.time())%10000}.mp4")

            progress_bar.value = 0.85
            txt_log.value = "[3/3] Ses ve müzik dengeleniyor..."
            page.update()

            if secili_muzik["yol"] and os.path.exists(secili_muzik["yol"]):
                orig_vol = "1.0" if tarz == "vlog" else "0.20"
                mus_vol = "0.15" if tarz == "vlog" else "0.85"
                ffmpeg_komut_calistir([
                    "ffmpeg", "-y", "-i", ham_video, "-stream_loop", "-1", "-i", secili_muzik["yol"],
                    "-filter_complex", f"[0:a]volume={orig_vol}[a0];[1:a]volume={mus_vol}[a1];[a0][a1]amix=inputs=2:duration=first[aout]",
                    "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", cikti_yolu
                ])
            else:
                shutil.copy2(ham_video, cikti_yolu)

            son_cikti["yol"] = cikti_yolu
            progress_bar.value = 1.0
            txt_log.value = f"✔ Tamamlandı!\nKayıt Yeri: {cikti_yolu}"
        except Exception as ex:
            txt_log.value = f"Hata: {str(ex)}"
        finally:
            btn_baslat.disabled = False
            shutil.rmtree(gecici, ignore_errors=True)
            page.update()

    def baslat_tiklandi(e):
        threading.Thread(target=kurguyu_isle, daemon=True).start()

    btn_baslat = ft.ElevatedButton(
        "Otomatik Kurguyu Başlat",
        icon=ft.icons.AUTO_FIX_HIGH,
        bgcolor="#238636",
        color="#ffffff",
        height=48,
        width=400,
        on_click=baslat_tiklandi,
    )

    page.add(
        ft.Column(
            [
                ft.Text("STUDIO CUT", size=24, weight=ft.FontWeight.BOLD, color="#f0f6fc"),
                ft.Text("Mobil Akıllı Video Kurgu Motoru", size=12, color="#58a6ff"),
                ft.Divider(color="#30363d"),
                ft.ElevatedButton(
                    "1. Galeriden Videoları Seç",
                    icon=ft.icons.VIDEO_LIBRARY,
                    bgcolor="#1f6feb",
                    color="#ffffff",
                    width=400,
                    height=42,
                    on_click=lambda _: video_picker.pick_files(allow_multiple=True, file_type=ft.FilePickerFileType.VIDEO),
                ),
                txt_video_durum,
                ft.ElevatedButton(
                    "2. Müzik Seç (İsteğe Bağlı)",
                    icon=ft.icons.MUSIC_NOTE,
                    bgcolor="#21262d",
                    color="#ffffff",
                    width=400,
                    height=40,
                    on_click=lambda _: muzik_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.AUDIO),
                ),
                txt_muzik_durum,
                dd_tarz,
                dd_oran,
                ft.Text("Kurgu Sıkılığı:", size=12, color="#c9d1d9"),
                slider_siklik,
                txt_talimat,
                btn_baslat,
                progress_bar,
                ft.Container(
                    content=txt_log,
                    bgcolor="#161b22",
                    padding=12,
                    border_radius=8,
                    border=ft.border.all(1, "#30363d"),
                ),
            ],
            spacing=10,
        )
    )


ft.app(target=main)
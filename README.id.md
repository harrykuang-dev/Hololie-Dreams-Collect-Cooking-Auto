# Hololive Dreams Auto Collect Cooking — 1.0.1

[English](README.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Indonesian](README.id.md) · [简体中文](README.zh-CN.md)

Program memasak otomatis untuk Collect Cooking pada *hololive Dreams* versi Windows. Program mengenali bahan dari layar game, memilihnya melalui input mouse biasa, lalu melanjutkan permainan setelah layar hasil.

## Unduh

Buka [GitHub Releases](https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto/releases/tag/v1.0.1) dan unduh semua bagian `Collect-Cooking-Auto-v1.0.1-win64.7z.*` ke folder yang sama. Ekstrak `.7z.001` dengan 7-Zip, lalu jalankan `Collect-Cooking-Auto-v1.0.1.exe` di dalam folder hasil ekstraksi.

Pertahankan folder `_internal` di samping EXE. Python, pustaka inferensi dan kelima model sudah disertakan. Gunakan `SHA256SUMS.txt` untuk memeriksa unduhan. `models.zip` ditujukan untuk menjalankan kode sumber. ZIP sumber dari GitHub memerlukan pemasangan dependensi dan model secara terpisah.

## Fitur

- Mengenali resep, jumlah bahan yang masih diperlukan dan isi slot, lalu merencanakan pengambilan bahan, pencocokan tiga benda dan pengocokan piring.
- Pilihan **Standar** (ResNet18) dan **Lanjutan** (ResNet101). Standar membutuhkan komputasi lebih rendah; Lanjutan sesuai untuk komputer yang lebih bertenaga.
- Pemuatan model terpisah dari mulai bermain. Model klasifikasi titik yang dimuat juga memverifikasi kandidat tambahan sesuai kebutuhan.
- Target jumlah permainan, kelanjutan otomatis setelah satu permainan selesai, dan berhenti ketika target tercapai.
- Enam bahasa antarmuka: Inggris, Mandarin Tradisional, Jepang, Korea, Indonesia dan Mandarin Sederhana. Pilihan bahasa berlaku pada antarmuka program.
- Pintasan yang dapat diubah, catatan aktivitas dan diagnostik lokal opsional.

## Penggunaan

1. Buka game dan masuk ke Collect Cooking.
2. Jalankan EXE, pilih bahasa dan model, lalu masukkan target permainan berupa bilangan bulat positif. Nilai awalnya lima permainan.
3. Klik **Muat model** dan tunggu hingga siap.
4. Klik **Mulai** agar program mencoba memulihkan jendela game dan membawanya ke depan, atau tekan **F8** di dalam game. Jika Windows memblokir perpindahan, kembali ke game secara manual. Pastikan jendela game tidak tertutup.
5. **F8** menjeda/melanjutkan; **Esc** atau **Hentikan** mengakhiri sesi. Beralih ke jendela lain menjeda input. Kembali ke game lalu tekan F8 untuk melanjutkan. Hentikan sebelum memilih dan memuat model lain.

Klik kolom pintasan, lalu tekan tombol atau kombinasi Ctrl/Alt/Shift yang diinginkan. Meninggalkan kolom sebelum menyelesaikan input mempertahankan pengaturan sebelumnya. Pengaturan disimpan untuk sesi berikutnya.

## Persyaratan dan batasan

Memerlukan Windows 10/11 x64 dan game versi Windows. Gunakan area game 16:9, pertahankan monitor menyala dan game terlihat. NVIDIA CUDA dipilih otomatis jika tersedia; jika tidak, inferensi memakai CPU. Pilih Standar terlebih dahulu pada komputer dengan sumber daya terbatas.

Folder hasil ekstraksi memakai sekitar 5,3 GB. Sediakan ruang tambahan untuk unduhan dan ekstraksi. Jumlah permainan selesai menunjukkan kemajuan sesi; lihat jumlah masakan dan skor pada layar hasil game. Gerakan bahan, objek yang saling menutupi, performa komputer dan pembaruan game dapat memengaruhi pengenalan.

## Implementasi teknis

### Pengambilan dan pemrosesan gambar

[Modul tangkapan](outputs/kitchen-bot/async_recording.py) memakai Windows GDI pada thread tersendiri dan meminta 20 frame per detik. Gambar terbaru diteruskan ke pengenalan tanpa menunggu enkode video. [Alur pengenalan](outputs/kitchen-bot/perception.py) menormalkan gambar menjadi 1536×864 dan melakukan segmentasi pada potongan papan 448×280. Titik klik dipetakan kembali dengan skala dan offset vertikal yang terukur.

### Pengenalan bahan dan model bersama

Model segmentasi utama menghasilkan area bahan yang terlihat. Model klasifikasi titik pilihan memeriksa potongan 64×64 di sekitar klik, yang diubah menjadi 96×96 untuk inferensi. Model ikon bersama membaca resep dan slot; templat angka serta gambar UI tetap menentukan jumlah kebutuhan dan keadaan layar.

Saat jalur utama akan menunggu atau mengocok piring, [pencari tambahan](outputs/kitchen-bot/supplemental_food.py) dapat mencari kandidat bawang bombai, udang goreng dan kaleng tuna sesuai kebutuhan. Model klasifikasi titik yang sudah dimuat memverifikasinya. Hanya model titik Standar atau Lanjutan yang dipilih yang dimuat. Lihat [rincian model](docs/model-options.md).

### Perencanaan dan jeda pengocokan

[Perencana](outputs/kitchen-bot/planner.py) mempertahankan resep, perkiraan slot, pengambilan yang menunggu konfirmasi dan lokasi kegagalan terbaru. Bahan yang diperlukan dan pencocokan tiga benda diprioritaskan. Perubahan jumlah kebutuhan dan tampilan slot memberi umpan balik. Pengocokan memerlukan jeda minimal lima detik antara penekanan tombol sebenarnya serta tombol yang siap pada gambar terbaru.

### Verifikasi gerakan dan kelanjutan

[Aliran optik](outputs/kitchen-bot/motion.py) memperkirakan gerakan sebelum klik. [Verifikasi gambar baru](outputs/kitchen-bot/latest_click.py) memeriksa pesanan, keadaan layar serta kelas bahan pada titik teramati dan titik prediksi. Pencarian ulang lokal terbatas dapat mencoba lagi bahan yang diperlukan setelah pelacakan gagal. [Kontrol sesi](outputs/kitchen-bot/session_flow.py) mengenali tombol lanjut di kanan bawah untuk berpindah dari hasil dan menu ke permainan berikutnya.

## Laporan masalah dan mode pengembang

Laporkan masalah pengenalan, klik atau kelanjutan melalui [GitHub Issues](https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto/issues). Aktifkan **Mode pengembang** sebelum mengulangi masalah. Hasil pengenalan, waktu klik, gambar game dan ringkasan performa disimpan secara lokal. Mode ini menambah beban pemrosesan; data tidak diunggah otomatis.

Klik `?` di sebelahnya untuk melihat dan membuka folder diagnostik:

```text
%LOCALAPPDATA%\CollectCookingAuto\sessions\
```

ZIP bertanggal dibuat saat sesi berakhir. Sertakan versi program, model pilihan, bahasa game, resolusi, skala tampilan Windows, deskripsi masalah dan ZIP diagnostik.

## Sumber dan pemberitahuan

Panduan menjalankan sumber, membangun dan menguji tersedia di [panduan pengembangan](docs/DEVELOPMENT.md). Lihat juga [riwayat versi](docs/VERSION_HISTORY.md), [rincian model](docs/model-options.md) dan [istilah game](docs/GAME_TERMS.md).

Lisensi pihak ketiga tersimpan di [third-party](third-party/README.md). Hak atas nama dan gambar game dimiliki pemegang hak masing-masing.

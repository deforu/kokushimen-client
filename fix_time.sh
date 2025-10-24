#!/bin/bash

# =============================================================================
# 時刻修正スクリプト（Raspberry Pi用）
# =============================================================================

# 色付きメッセージ用の関数
print_info() {
    echo -e "\033[36m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[32m[SUCCESS]\033[0m $1"
}

print_warning() {
    echo -e "\033[33m[WARNING]\033[0m $1"
}

print_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

echo "🕒 Raspberry Pi 時刻修正スクリプト"
echo "=================================="

print_info "現在のシステム時刻: $(date)"
print_info "現在のハードウェア時刻: $(sudo hwclock --show 2>/dev/null || echo '取得できませんでした')"

echo ""
echo "🔧 時刻修正方法を選択してください："
echo "1) 自動同期（インターネット経由）"
echo "2) 手動設定"
echo "3) ハードウェア時刻から復元"
echo "4) 時刻確認のみ"
read -p "選択してください [1-4]: " choice

case $choice in
    1)
        print_info "インターネットから時刻を自動同期しています..."
        
        # NTPサービスの停止
        sudo systemctl stop ntp 2>/dev/null || true
        sudo systemctl stop systemd-timesyncd 2>/dev/null || true
        
        # 手動同期の実行
        if sudo ntpdate -s time.nist.gov 2>/dev/null; then
            print_success "NIST時刻サーバーからの同期に成功"
        elif sudo ntpdate -s pool.ntp.org 2>/dev/null; then
            print_success "NTP poolからの同期に成功"
        elif sudo ntpdate -s time.google.com 2>/dev/null; then
            print_success "Google時刻サーバーからの同期に成功"
        else
            print_error "自動同期に失敗しました"
            echo "手動設定を試してください"
            exit 1
        fi
        
        # ハードウェア時刻の更新
        sudo hwclock --systohc 2>/dev/null || print_warning "ハードウェア時刻の更新に失敗"
        
        # NTPサービスの再開
        sudo systemctl start ntp 2>/dev/null || sudo systemctl start systemd-timesyncd 2>/dev/null || true
        ;;
        
    2)
        print_info "手動で時刻を設定します"
        echo "形式: YYYY-MM-DD HH:MM:SS"
        echo "例: 2025-09-15 12:30:00"
        read -p "正しい日時を入力してください: " manual_time
        
        if sudo date -s "$manual_time" 2>/dev/null; then
            print_success "手動設定に成功"
            # ハードウェア時刻の更新
            sudo hwclock --systohc 2>/dev/null || print_warning "ハードウェア時刻の更新に失敗"
        else
            print_error "日時の形式が正しくありません"
            exit 1
        fi
        ;;
        
    3)
        print_info "ハードウェア時刻からシステム時刻を復元します"
        if sudo hwclock --hctosys 2>/dev/null; then
            print_success "ハードウェア時刻からの復元に成功"
        else
            print_error "ハードウェア時刻の読み取りに失敗"
            exit 1
        fi
        ;;
        
    4)
        print_info "時刻確認のみです。変更は行いません。"
        ;;
        
    *)
        print_error "無効な選択です"
        exit 1
        ;;
esac

echo ""
print_success "更新後の時刻情報:"
print_info "システム時刻: $(date)"
print_info "ハードウェア時刻: $(sudo hwclock --show 2>/dev/null || echo '取得できませんでした')"
print_info "タイムゾーン: $(timedatectl show --property=Timezone --value 2>/dev/null || echo '取得できませんでした')"

echo ""
print_info "時刻修正が完了しました。"
print_info "パッケージ更新を実行する場合:"
echo "sudo apt update && sudo apt upgrade"

#!/usr/bin/env bash
# Instala o APK num emulador SEM internet, abre o app e espera o backend Python ficar pronto.
# Uso: scripts/testar_apk.sh HealthFlow.apk [captura.png]
set -u
APK="$1"
CAPTURA="${2:-apk.png}"

adb install -r "$APK" || exit 1
adb shell svc wifi disable
adb shell svc data disable
adb logcat -c
adb shell am start -W -n com.healthflow.app/.MainActivity

resultado=1
for _ in $(seq 1 60); do  # até 10 minutos
  sleep 10
  log=$(adb logcat -d -s chromium:* 2>/dev/null)
  if grep -q "HealthFlow: falha" <<<"$log"; then
    echo "$log" | grep "HealthFlow"
    break
  fi
  if grep -q "HealthFlow: backend pronto" <<<"$log"; then
    resultado=0
    break
  fi
done

sleep 5
adb exec-out screencap -p > "$CAPTURA"
if adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; then
  adb exec-out cat /sdcard/ui.xml | grep -o 'text="[^"]\+"' | head -20
fi
adb logcat -d -s chromium:* | tail -30
if [ $resultado -ne 0 ]; then
  # Anotações do GitHub Actions: o diagnóstico aparece no resumo do job.
  anotar() { echo "::error title=$1::$(printf '%s' "$2" | tail -c 3500 | sed ':a;N;$!ba;s/%/%25/g;s/\r//g;s/\n/%0A/g')"; }
  anotar "logcat chromium" "$(adb logcat -d -s chromium:* | tail -40)"
  anotar "logcat erros" "$(adb logcat -d '*:E' | grep -iv 'audio\|bluetooth\|wifi\|gnss' | tail -40)"
  anotar "processo" "$(adb shell pidof com.healthflow.app || echo 'app não está rodando')"
fi
[ $resultado -eq 0 ] && echo "OK: o app carregou o backend sem internet" || echo "FALHOU: o backend não ficou pronto"
exit $resultado

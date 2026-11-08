#!/bin/bash
# Model-proxy labeling (NOT expert labels): one model labels the Golden Dataset in isolation,
# seeing only what human experts get. Usage:
#   evals/golden/proxy_label.sh claude-sonnet-5-5 sonnet-5-5 "$PWD" evals/golden/labeling/model-proxy
set -e
MODEL=$1; NAME=$2; REPO=$3; OUT=$4
WS=$(mktemp -d -t labeler-$NAME-XXXX)
cp $REPO/evals/golden/labeling/tasks.md $REPO/evals/golden/labeling/template.csv $REPO/evals/golden/LABELING.md \
   $REPO/skills/backlog-prioritization-engine/references/scoring-rubric.md $WS/
cd $WS
PROMPT="Ты эксперт по приоритизации бэклога платформы Development Center. Выполни разметку строго по инструкции LABELING.md в этой папке: прочитай tasks.md (карточки задач) и scoring-rubric.md (веса и шкалы), заполни template.csv для всех 24 задач и сохрани результат как ./expert-$NAME.csv: те же колонки и порядок, разделитель ';', кодировка UTF-8. Для critical=yes заполни critical_reason и оставь Impact, urgency и relevance пустыми. Работай самостоятельно, ничего не спрашивай, скрипты не запускай."
timeout 1200 claude -p "$PROMPT" --model $MODEL --output-format json --strict-mcp-config --setting-sources project \
  --allowedTools Read Write Glob > $OUT/labeler-$NAME.json 2> $OUT/labeler-$NAME.err
cp $WS/expert-$NAME.csv $OUT/ && echo "done $NAME"
rm -rf $WS

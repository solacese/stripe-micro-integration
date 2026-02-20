{{- define "stripe-solace-bridge.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name "stripe-solace-bridge" | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

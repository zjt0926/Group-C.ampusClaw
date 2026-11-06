# 一键复查入口：SEC-05 密钥扫描 + SEC-06 依赖审计
# 用法：make check-security（分项：make check-secrets / make audit-deps）

.PHONY: check-security check-secrets audit-deps

check-security: check-secrets audit-deps

check-secrets:
	@sh scripts/check_security.sh secrets

audit-deps:
	@sh scripts/check_security.sh deps

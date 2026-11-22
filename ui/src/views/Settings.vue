<!--
  Copyright (C) 2022 Nethesis S.r.l.
  SPDX-License-Identifier: GPL-3.0-or-later
-->
<template>
  <cv-grid fullWidth>
    <cv-row>
      <cv-column class="page-title">
        <h2>{{ $t("settings.title") }}</h2>
      </cv-column>
    </cv-row>
    <cv-row v-if="error.getConfiguration">
      <cv-column>
        <NsInlineNotification
          kind="error"
          :title="$t('action.get-configuration')"
          :description="error.getConfiguration"
          :showCloseButton="false"
        />
      </cv-column>
    </cv-row>
    <cv-row>
      <cv-column>
        <cv-tile light>
          <cv-form @submit.prevent="configureModule">
            <cv-text-input
              :label="$t('settings.wikijs_fqdn')"
              placeholder="wikijs.example.org"
              v-model.trim="host"
              class="mg-bottom"
              :invalid-message="error.host"
              :disabled="loading.getConfiguration || loading.configureModule"
              ref="host"
            >
            </cv-text-input>
            <NsToggle
              value="letsEncrypt"
              :label="core.$t('apps_lets_encrypt.request_https_certificate')"
              v-model="isLetsEncryptEnabled"
              :disabled="stillLoading"
              class="mg-bottom"
            >
              <template #tooltip>
                <div class="mg-bottom-sm">
                  {{ core.$t("apps_lets_encrypt.lets_encrypt_tips") }}
                </div>
                <div class="mg-bottom-sm">
                  <cv-link @click="goToCertificates">
                    {{ core.$t("apps_lets_encrypt.go_to_tls_certificates") }}
                  </cv-link>
                </div>
              </template>
              <template slot="text-left">{{
                $t("settings.disabled")
              }}</template>
              <template slot="text-right">{{
                $t("settings.enabled")
              }}</template>
            </NsToggle>
            <cv-row
              v-if="isLetsEncryptCurrentlyEnabled && !isLetsEncryptEnabled"
            >
              <cv-column>
                <NsInlineNotification
                  kind="warning"
                  :title="
                    core.$t('apps_lets_encrypt.lets_encrypt_disabled_warning')
                  "
                  :description="
                    core.$t(
                      'apps_lets_encrypt.lets_encrypt_disabled_warning_description',
                      {
                        node: this.status.node_ui_name
                          ? this.status.node_ui_name
                          : this.status.node,
                      }
                    )
                  "
                  :showCloseButton="false"
                />
              </cv-column>
            </cv-row>
            <cv-toggle
              value="httpToHttps"
              :label="$t('settings.http_to_https')"
              v-model="isHttpToHttpsEnabled"
              :disabled="loading.getConfiguration || loading.configureModule"
              class="mg-bottom"
            >
              <template slot="text-left">{{
                $t("settings.disabled")
              }}</template>
              <template slot="text-right">{{
                $t("settings.enabled")
              }}</template>
            </cv-toggle>
            <h3 class="mg-bottom">{{ $t("settings.admin_heading") }}</h3>
            <p class="mg-bottom">{{ $t("settings.admin_help") }}</p>
            <NsTextInput
              v-model.trim="adminEmail"
              :label="$t('settings.admin_email')"
              placeholder="admin@example.org"
              :invalid-message="error.admin_email"
              :disabled="stillLoading"
              autocomplete="off"
              class="mg-bottom"
              ref="admin_email"
            />
            <NsTextInput
              v-model="adminPassword"
              type="password"
              :label="$t('settings.admin_password')"
              :invalid-message="error.admin_password"
              :helper-text="
                adminPasswordSet
                  ? $t('settings.admin_password_saved')
                  : $t('settings.admin_password_help')
              "
              :disabled="stillLoading"
              autocomplete="new-password"
              class="mg-bottom"
              ref="admin_password"
            />
            <h3 class="mg-bottom">{{ $t("settings.sites") }}</h3>
            <p class="mg-bottom">{{ $t("settings.sites_help") }}</p>
            <div v-for="(site, index) in sites" :key="index" class="mg-bottom">
              <NsTextInput
                v-model.trim="site.host"
                :label="$t('settings.site_hostname')"
                :disabled="stillLoading"
                class="mg-bottom"
              />
              <NsCheckbox
                v-model="site.lets_encrypt"
                :label="$t('settings.site_certificate')"
                :disabled="stillLoading"
              />
              <NsButton
                type="button"
                kind="ghost"
                :icon="TrashCan20"
                :disabled="stillLoading"
                @click="sites.splice(index, 1)"
              >
                {{ $t("settings.remove_site") }}
              </NsButton>
            </div>
            <NsButton
              type="button"
              kind="secondary"
              :icon="Add20"
              :disabled="stillLoading || sites.length >= 30"
              class="mg-bottom"
              @click="sites.push({ host: '', lets_encrypt: false })"
            >
              {{ $t("settings.add_site") }}
            </NsButton>
            <NsInlineNotification
              v-if="error.sites"
              kind="error"
              :title="$t('settings.sites')"
              :description="error.sites"
              :showCloseButton="false"
            />
            <h3 class="mg-bottom">{{ $t("settings.auth_heading") }}</h3>
            <cv-select
              v-model="auth.ldap_domain"
              :label="$t('settings.ldap_domain')"
              :disabled="stillLoading"
              class="mg-bottom"
            >
              <cv-select-option value="">{{
                $t("settings.disabled")
              }}</cv-select-option>
              <cv-select-option
                v-for="name in ldapDomains"
                :key="name"
                :value="name"
                >{{ name }}</cv-select-option
              >
            </cv-select>
            <cv-select
              v-model="auth.oidc_mode"
              :label="$t('settings.oidc_mode')"
              :disabled="stillLoading"
              class="mg-bottom"
            >
              <cv-select-option value="off">{{
                $t("settings.disabled")
              }}</cv-select-option>
              <cv-select-option value="ns8">{{
                $t("settings.oidc_ns8")
              }}</cv-select-option>
              <cv-select-option value="manual">{{
                $t("settings.oidc_manual")
              }}</cv-select-option>
            </cv-select>
            <template v-if="auth.oidc_mode === 'ns8'">
              <cv-select
                v-model="auth.provider"
                :label="$t('settings.oidc_provider')"
                :disabled="stillLoading"
                @change="auth.oidc_domain = ''"
                class="mg-bottom"
              >
                <cv-select-option value="" disabled>{{
                  $t("settings.oidc_pick")
                }}</cv-select-option>
                <cv-select-option
                  v-for="provider in oidcProviders"
                  :key="provider.id"
                  :value="provider.id"
                  >{{ provider.label }} ({{
                    provider.module
                  }})</cv-select-option
                >
              </cv-select>
              <cv-select
                v-model="auth.oidc_domain"
                :label="$t('settings.oidc_domain')"
                :disabled="stillLoading"
                class="mg-bottom"
              >
                <cv-select-option value="" disabled>{{
                  $t("settings.oidc_pick")
                }}</cv-select-option>
                <cv-select-option
                  v-for="name in oidcDomains"
                  :key="name"
                  :value="name"
                  >{{ name }}</cv-select-option
                >
              </cv-select>
            </template>
            <cv-accordion v-if="auth.oidc_mode === 'manual'" class="mg-bottom">
              <cv-accordion-item :open="true">
                <template #title>{{ $t("settings.oidc_advanced") }}</template>
                <template #content>
                  <NsTextInput
                    v-model.trim="auth.issuer"
                    :label="$t('settings.oidc_issuer')"
                    :disabled="stillLoading"
                    class="mg-bottom"
                  />
                  <NsTextInput
                    v-model.trim="auth.client_id"
                    :label="$t('settings.oidc_client_id')"
                    :disabled="stillLoading"
                    class="mg-bottom"
                  />
                  <NsTextInput
                    v-model="auth.client_secret"
                    type="password"
                    :label="$t('settings.oidc_client_secret')"
                    :disabled="stillLoading"
                    :helper-text="
                      clientSecretSet ? $t('settings.oidc_saved_secret') : ''
                    "
                    autocomplete="new-password"
                  />
                </template>
              </cv-accordion-item>
            </cv-accordion>
            <p v-if="callbackUrl && auth.oidc_mode !== 'off'" class="mg-bottom">
              {{ $t("settings.callback_url") }} <code>{{ callbackUrl }}</code>
            </p>
            <template v-if="auth.ldap_domain || auth.oidc_mode !== 'off'">
              <NsCheckbox
                v-model="auth.registration"
                :label="$t('settings.registration')"
                :disabled="stillLoading"
                class="mg-bottom"
              />
              <NsCheckbox
                v-model="auth.trusted_email"
                :label="$t('settings.trusted_email')"
                :disabled="stillLoading"
                class="mg-bottom"
              />
              <p class="mg-bottom">{{ $t("settings.auth_setup") }}</p>
            </template>
            <NsInlineNotification
              v-if="error.auth"
              kind="error"
              :title="$t('settings.auth_heading')"
              :description="error.auth"
              :showCloseButton="false"
            />
            <cv-row v-if="error.configureModule">
              <cv-column>
                <NsInlineNotification
                  kind="error"
                  :title="$t('action.configure-module')"
                  :description="error.configureModule"
                  :showCloseButton="false"
                />
              </cv-column>
            </cv-row>
            <cv-row v-if="error.getStatus">
              <cv-column>
                <NsInlineNotification
                  kind="error"
                  :title="$t('action.get-status')"
                  :description="error.getStatus"
                  :showCloseButton="false"
                />
              </cv-column>
            </cv-row>
            <cv-row v-if="validationErrorDetails.length">
              <cv-column>
                <NsInlineNotification
                  kind="error"
                  :title="
                    core.$t('apps_lets_encrypt.cannot_obtain_certificate')
                  "
                  :showCloseButton="false"
                >
                  <template #description>
                    <div class="flex flex-col gap-2">
                      <div
                        v-for="(detail, index) in validationErrorDetails"
                        :key="index"
                      >
                        {{ detail }}
                      </div>
                    </div>
                  </template>
                </NsInlineNotification>
              </cv-column>
            </cv-row>
            <NsButton
              kind="primary"
              :icon="Save20"
              :loading="loading.configureModule"
              :disabled="loading.getConfiguration || loading.configureModule"
              >{{ $t("settings.save") }}</NsButton
            >
          </cv-form>
        </cv-tile>
      </cv-column>
    </cv-row>
  </cv-grid>
</template>

<script>
import to from "await-to-js";
import { mapState } from "vuex";
import {
  QueryParamService,
  UtilService,
  TaskService,
  IconService,
  PageTitleService,
} from "@nethserver/ns8-ui-lib";

export default {
  name: "Settings",
  mixins: [
    TaskService,
    IconService,
    UtilService,
    QueryParamService,
    PageTitleService,
  ],
  pageTitle() {
    return this.$t("settings.title") + " - " + this.appName;
  },
  data() {
    return {
      q: {
        page: "settings",
      },
      status: {},
      validationErrorDetails: [],
      urlCheckInterval: null,
      host: "",
      adminEmail: "",
      adminPassword: "",
      adminPasswordSet: false,
      auth: {
        ldap_domain: "",
        oidc_mode: "off",
        provider: "",
        oidc_domain: "",
        issuer: "",
        client_id: "",
        client_secret: "",
        registration: false,
        trusted_email: false,
      },
      sites: [],
      ldapDomains: [],
      oidcProviders: [],
      callbackUrl: "",
      clientSecretSet: false,
      isLetsEncryptEnabled: false,
      isLetsEncryptCurrentlyEnabled: false,
      isHttpToHttpsEnabled: true,
      loading: {
        getConfiguration: false,
        configureModule: false,
        getStatus: false,
      },
      error: {
        getConfiguration: "",
        configureModule: "",
        host: "",
        lets_encrypt: "",
        http2https: "",
        sites: "",
        auth: "",
        admin_email: "",
        admin_password: "",
        getStatus: "",
      },
    };
  },
  computed: {
    oidcDomains() {
      const selected = this.oidcProviders.find(
        (provider) => provider.id === this.auth.provider
      );
      return selected ? selected.domains : [];
    },
    ...mapState(["instanceName", "core", "appName"]),
    stillLoading() {
      return (
        this.loading.getConfiguration ||
        this.loading.configureModule ||
        this.loading.getStatus
      );
    },
  },
  created() {
    this.getConfiguration();
    this.getStatus();
  },
  beforeRouteEnter(to, from, next) {
    next((vm) => {
      vm.watchQueryData(vm);
      vm.urlCheckInterval = vm.initUrlBindingForApp(vm, vm.q.page);
    });
  },
  beforeRouteLeave(to, from, next) {
    clearInterval(this.urlCheckInterval);
    next();
  },
  methods: {
    goToCertificates() {
      this.core.$router.push("/settings/tls-certificates");
    },
    async getStatus() {
      this.loading.getStatus = true;
      this.error.getStatus = "";
      const taskAction = "get-status";
      const eventId = this.getUuid();
      // register to task error
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.getStatusAborted
      );
      // register to task completion
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.getStatusCompleted
      );
      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          extra: {
            title: this.$t("action." + taskAction),
            isNotificationHidden: true,
            eventId,
          },
        })
      );
      const err = res[0];
      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.getStatus = this.getErrorMessage(err);
        this.loading.getStatus = false;
        return;
      }
    },
    getStatusAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.getStatus = this.$t("error.generic_error");
      this.loading.getStatus = false;
    },
    getStatusCompleted(taskContext, taskResult) {
      this.status = taskResult.output;
      this.loading.getStatus = false;
    },
    async getConfiguration() {
      this.loading.getConfiguration = true;
      this.error.getConfiguration = "";
      const taskAction = "get-configuration";
      const eventId = this.getUuid();

      // register to task error
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.getConfigurationAborted
      );

      // register to task completion
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.getConfigurationCompleted
      );

      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          extra: {
            title: this.$t("action." + taskAction),
            isNotificationHidden: true,
            eventId,
          },
        })
      );
      const err = res[0];

      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.getConfiguration = this.getErrorMessage(err);
        this.loading.getConfiguration = false;
        return;
      }
    },
    getConfigurationAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.getConfiguration = this.$t("error.generic_error");
      this.loading.getConfiguration = false;
    },
    getConfigurationCompleted(taskContext, taskResult) {
      const config = taskResult.output;
      this.host = config.host;
      this.sites = (config.sites || []).map((site) => ({ ...site }));
      this.adminEmail = config.admin_email || "";
      this.adminPassword = "";
      this.adminPasswordSet = Boolean(config.admin_password_set);
      const { callback_url, client_secret_set, ...saved } = config.auth || {};
      this.auth = {
        ...this.auth,
        trusted_email: false,
        ...saved,
        client_secret: "",
      };
      this.callbackUrl = callback_url || "";
      this.clientSecretSet = Boolean(client_secret_set);
      this.ldapDomains = config.ldap_domains || [];
      this.oidcProviders = config.oidc_providers || [];
      this.isLetsEncryptEnabled = config.lets_encrypt;
      this.isLetsEncryptCurrentlyEnabled = config.lets_encrypt;
      this.isHttpToHttpsEnabled = config.http2https;

      this.loading.getConfiguration = false;
      this.focusElement("host");
    },
    validateConfigureModule() {
      this.clearErrors(this);
      this.validationErrorDetails = [];

      let isValidationOk = true;
      if (!this.host) {
        this.error.host = this.$t("common.required");

        if (isValidationOk) {
          this.focusElement("host");
        }
        isValidationOk = false;
      }
      if (this.adminPassword && this.adminPassword.length < 12) {
        this.error.admin_password = this.$t("settings.admin_password_length");
        if (isValidationOk) {
          this.focusElement("admin_password");
        }
        isValidationOk = false;
      }
      if (this.adminEmail && !this.adminPassword && !this.adminPasswordSet) {
        this.error.admin_password = this.$t("settings.admin_password_required");
        if (isValidationOk) {
          this.focusElement("admin_password");
        }
        isValidationOk = false;
      }
      return isValidationOk;
    },
    configureModuleValidationFailed(validationErrors) {
      this.loading.configureModule = false;
      let focusAlreadySet = false;
      for (const validationError of validationErrors) {
        const param = validationError.parameter;
        if (param === "sites" || param === "auth") {
          this.error[param] = this.$t("settings." + validationError.error);
          if (validationError.details) {
            this.error[param] += " " + validationError.details;
          }
        } else if (validationError.details) {
          // show inline error notification with details
          this.validationErrorDetails = validationError.details
            .split("\n")
            .filter((detail) => detail.trim() !== "");
        } else {
          // set i18n error message
          this.error[param] = this.$t("settings." + validationError.error);
          if (!focusAlreadySet) {
            this.focusElement(param);
            focusAlreadySet = true;
          }
        }
      }
    },
    async configureModule() {
      const isValidationOk = this.validateConfigureModule();
      if (!isValidationOk) {
        return;
      }

      this.loading.configureModule = true;
      const taskAction = "configure-module";
      const adminData = {};
      if (this.adminEmail) {
        adminData.admin_email = this.adminEmail;
      }
      if (this.adminPassword) {
        // write-only: sent only when the administrator types a new one
        adminData.admin_password = this.adminPassword;
      }
      const eventId = this.getUuid();

      // register to task error
      this.core.$root.$once(
        `${taskAction}-aborted-${eventId}`,
        this.configureModuleAborted
      );

      // register to task validation
      this.core.$root.$once(
        `${taskAction}-validation-failed-${eventId}`,
        this.configureModuleValidationFailed
      );

      // register to task completion
      this.core.$root.$once(
        `${taskAction}-completed-${eventId}`,
        this.configureModuleCompleted
      );
      const res = await to(
        this.createModuleTaskForApp(this.instanceName, {
          action: taskAction,
          data: {
            host: this.host,
            auth: { ...this.auth },
            sites: this.sites.map((site) => ({ ...site })),
            lets_encrypt: this.isLetsEncryptEnabled,
            http2https: this.isHttpToHttpsEnabled,
            ...adminData,
          },
          extra: {
            title: this.$t("settings.instance_configuration", {
              instance: this.instanceName,
            }),
            description: this.$t("settings.configuring"),
            eventId,
          },
        })
      );
      const err = res[0];

      if (err) {
        console.error(`error creating task ${taskAction}`, err);
        this.error.configureModule = this.getErrorMessage(err);
        this.loading.configureModule = false;
        return;
      }
    },
    configureModuleAborted(taskResult, taskContext) {
      console.error(`${taskContext.action} aborted`, taskResult);
      this.error.configureModule = this.$t("error.generic_error");
      this.loading.configureModule = false;
    },
    configureModuleCompleted() {
      this.loading.configureModule = false;
      this.adminPassword = "";

      // reload configuration
      this.getConfiguration();
    },
  },
};
</script>

<style scoped lang="scss">
@import "../styles/carbon-utils";
.mg-bottom {
  margin-bottom: $spacing-06;
}

.maxwidth {
  max-width: 38rem;
}
</style>

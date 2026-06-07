<script setup>
import { computed, ref } from 'vue'

import { addDataSourceAgent } from '../../../lib/api'

const props = defineProps({
  catalog: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['refresh'])

const agentMessages = ref([
  {
    role: 'agent',
    content: '我是数据源智能体。你可以直接告诉我“新增数据源 xxx，主源 yfinance，fallback mock”，我会把它写进当前配置。',
  },
])
const agentInput = ref('')
const agentBusy = ref(false)
const pendingSource = ref(null)
const localError = ref('')

const sources = computed(() => props.catalog?.sources || [])
const timeouts = computed(() => props.catalog?.timeouts || null)
const retry = computed(() => props.catalog?.retry || null)

async function sendAgentMessage() {
  const content = agentInput.value.trim()
  if (!content || agentBusy.value) {
    return
  }

  agentMessages.value.push({ role: 'user', content })
  localError.value = ''
  agentBusy.value = true

  try {
    const response = await addDataSourceAgent({
      message: content,
      conversation: agentMessages.value.slice(0, -1).map((item) => ({
        role: item.role === 'agent' ? 'assistant' : 'user',
        content: item.content,
      })),
    })
    pendingSource.value = response.saved_source
    agentMessages.value.push({ role: 'agent', content: response.assistant_message })
    await emit('refresh')
  } catch (error) {
    localError.value = error instanceof Error ? error.message : '新增数据源失败'
    agentMessages.value.push({ role: 'agent', content: localError.value })
  } finally {
    agentBusy.value = false
    agentInput.value = ''
  }
}
</script>

<template>
  <section class="view-stack bull-strategy-stack">
    <section class="panel strategy-current-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Data Sources</p>
          <h2>当前数据源目录</h2>
        </div>
        <span class="panel-meta">{{ loading ? '刷新中' : `${sources.length} 个 source key` }}</span>
      </div>

      <div class="strategy-current-grid">
        <article class="strategy-metric-card">
          <span>数据源数</span>
          <strong>{{ sources.length }}</strong>
        </article>
        <article class="strategy-metric-card">
          <span>连接超时</span>
          <strong>{{ timeouts ? `${timeouts.connect_seconds}s` : '--' }}</strong>
        </article>
        <article class="strategy-metric-card">
          <span>读取超时</span>
          <strong>{{ timeouts ? `${timeouts.read_seconds}s` : '--' }}</strong>
        </article>
        <article class="strategy-metric-card">
          <span>重试次数</span>
          <strong>{{ retry ? retry.max_attempts : '--' }}</strong>
        </article>
      </div>

      <p class="strategy-description">
        这里展示当前 `data_sources.yaml` 中的 source key。下方智能体对话框会把你的自然语言解析成结构化配置，并直接写入当前数据源配置文件。
      </p>

      <div class="strategy-action-row">
        <button class="ghost-button" type="button" :disabled="loading" @click="emit('refresh')">
          {{ loading ? '刷新中...' : '刷新数据源列表' }}
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Catalog</p>
          <h2>已配置数据源</h2>
        </div>
        <span class="panel-meta">按 source key 排序</span>
      </div>

      <div class="data-table-wrap">
        <table class="data-table compact-table">
          <thead>
            <tr>
              <th>Source Key</th>
              <th>Primary</th>
              <th>Fallback</th>
              <th>Backup</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in sources" :key="item.name">
              <td><strong>{{ item.name }}</strong></td>
              <td>{{ item.primary }}</td>
              <td>{{ item.fallback || '--' }}</td>
              <td>{{ item.backup || '--' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel agent-dialog">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Agent</p>
          <h2>数据源对话智能体</h2>
        </div>
        <span class="panel-meta">直接新增 source key</span>
      </div>

      <div class="agent-message-list">
        <article v-for="(message, index) in agentMessages" :key="index" class="agent-message" :class="message.role">
          <strong>{{ message.role === 'agent' ? '智能体' : '你' }}</strong>
          <p>{{ message.content }}</p>
        </article>
      </div>

      <div class="form-stack">
        <label class="toolbar-field">
          <span>告诉智能体你要新增什么数据源</span>
          <textarea v-model="agentInput" rows="4" placeholder="例如：新增数据源 news_feed，主源 alphavantage，fallback fmp"></textarea>
        </label>
      </div>

      <div v-if="pendingSource" class="agent-plan-summary agent-plan-preview">
        <strong>已写入 {{ pendingSource.name }}</strong>
        <small>primary：{{ pendingSource.primary }}</small>
        <small>fallback：{{ pendingSource.fallback || '--' }}</small>
        <small>backup：{{ pendingSource.backup || '--' }}</small>
      </div>

      <div v-if="localError" class="banner banner-error">{{ localError }}</div>

      <div class="strategy-action-row">
        <button class="primary-button" type="button" :disabled="agentBusy" @click="sendAgentMessage">
          {{ agentBusy ? '写入中...' : '发送并新增数据源' }}
        </button>
      </div>
    </section>
  </section>
</template>

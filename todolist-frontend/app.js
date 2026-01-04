const { createApp } = Vue;

createApp({
  data() {
    return {
      nlText: '',
      todos: [],
      currentTimeDisplay: '',
      currentTimeISO: '',
      weekStart: new Date(),
      weekDates: [],
      hours: Array.from({ length: 24 }, (_, i) => (6 + i) % 24),
      weekTodos: [],
      newTitle: '',
      newMinute: '00',
      showTodoList: true,
      selectedTask: null,
    }
  },
  mounted() {
    this.weekStart = this.startOfWeek(new Date())
    this.loadTodos()
    this.buildWeek()
    this.updateCurrentTime()
    this._timeTimer = setInterval(this.updateCurrentTime, 1000)
    window.addEventListener('keydown', this.handleKeyDown)
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this.handleKeyDown)
    if (this._timeTimer) clearInterval(this._timeTimer)
  },
  methods: {
    splitDue(due) {
      if (!due) return { date: '', time: '' }

      if (typeof due === 'string' && due.includes('T')) {
        const [d, tRaw] = due.split('T')
        let t = tRaw || ''
        t = t.replace(/Z$/i, '')
        t = t.replace(/[+-]\d{2}:?\d{2}$/, '')
        const match = t.match(/\d{2}:\d{2}(?::\d{2})?/)
        return { date: d, time: match ? match[0] : '' }
      }
      try {
        const dt = new Date(due)
        if (!isNaN(dt.getTime())) {
          const date = dt.toLocaleDateString()
          const time = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          return { date, time }
        }
      } catch (_) { }

      if (typeof due === 'string' && due.includes(' ')) {
        const [date, time] = due.split(' ')
        return { date, time: time || '' }
      }

      return { date: String(due), time: '' }
    },
    async loadTodos() {
      try {
        const res = await fetch('http://localhost:8000/todos')
        this.todos = await res.json()
        this.markTodosForWeek()
      } catch (err) {
        console.error(err)
        alert('无法从后端加载待办，请确认后端已启动（http://localhost:8000）')
      }
    },

    updateCurrentTime() {
      const now = new Date()

      const pad = (n) => String(n).padStart(2, '0')
      const display = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
      this.currentTimeDisplay = display
      this.currentTimeISO = now.toISOString()
    },

    startOfWeek(date) {
      const d = new Date(date)
      const day = d.getDay()
      d.setDate(d.getDate() - day)
      d.setHours(0, 0, 0, 0)
      return d
    },

    buildWeek() {
      const start = new Date(this.weekStart)
      const days = []
      for (let i = 0; i < 7; i++) {
        const d = new Date(start)
        d.setDate(start.getDate() + i)
        days.push(this.formatDate(d))
      }
      this.weekDates = days
      this.markTodosForWeek()
    },

    prevWeek() { this.weekStart.setDate(this.weekStart.getDate() - 7); this.buildWeek() },
    nextWeek() { this.weekStart.setDate(this.weekStart.getDate() + 7); this.buildWeek() },

    formatDayHeader(day) {
      const dt = new Date(day)
      const wk = ['日', '一', '二', '三', '四', '五', '六'][dt.getDay()]
      return `周${wk} ${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
    },

    formatDate(dt) {
      const y = dt.getFullYear()
      const m = String(dt.getMonth() + 1).padStart(2, '0')
      const d = String(dt.getDate()).padStart(2, '0')
      return `${y}-${m}-${d}`
    },

    async markTodosForWeek() {
      if (!this.todos || !this.weekDates || this.weekDates.length === 0) return
      const set = new Set(this.weekDates)
      this.weekTodos = this.todos.filter(t => t.due_date && set.has(String(t.due_date).slice(0, 10)))
    },

    tasksInCell(day, h) {
      return (this.weekTodos || []).filter(t => {
        if (!t.due_date) return false
        const d = String(t.due_date).slice(0, 10)
        if (d !== day) return false

        const m = t.due_date.match(/T(\d{2}):(\d{2})/)
        if (m) {
          const hh = parseInt(m[1], 10)
          return hh === h
        }

        return h === 0
      })
    },

    getMinute(task) {
      if (!task.due_date) return 0
      const m = String(task.due_date).match(/T(\d{2}):(\d{2})/)
      if (m) return parseInt(m[2], 10)
      return 0
    },

    taskTop(task) {
      const min = this.getMinute(task)
      return (min / 60 * 100) + '%'
    },

    async onHourClick(day, h) {

      const title = prompt(`为 ${day} ${String(h).padStart(2, '0')}:00 输入标题：`)
      if (!title) return
      let minute = prompt('分钟（0-59，可留空默认为00）', '00')
      if (minute === null) minute = '00'
      minute = String(minute).padStart(2, '0')
      if (!/^\d{2}$/.test(minute) || Number(minute) < 0 || Number(minute) > 59) minute = '00'
      const due = `${day}T${String(h).padStart(2, '0')}:${minute}:00`
      try {
        const res = await fetch('http://localhost:8000/todos', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: title.trim(), description: null, due_date: due, tags: [], priority: 0 })
        })
        if (!res.ok) throw new Error(await res.text())
        const created = await res.json()
        this.todos.unshift(created)
        this.markTodosForWeek()
      } catch (err) {
        console.error(err)
        alert('添加失败：' + err.message)
      }
    },

    openTask(task) {

      const copy = Object.assign({}, task)
      copy.tags_str = (copy.tags && Array.isArray(copy.tags)) ? copy.tags.join(', ') : (copy.tags || '')

      copy.priority = (typeof copy.priority === 'number') ? copy.priority : (copy.priority ? Number(copy.priority) : 0)
      this.selectedTask = copy
    },

    closeTask() {
      this.selectedTask = null
    },

    handleKeyDown(e) {
      if (e.key === 'Escape' || e.key === 'Esc') {
        if (this.selectedTask) this.closeTask()
      }
    },

    async saveTask() {
      if (!this.selectedTask) return
      const payload = {
        title: this.selectedTask.title,
        description: this.selectedTask.description,
        due_date: this.selectedTask.due_date,
        tags: this.selectedTask.tags_str ? this.selectedTask.tags_str.split(',').map(s => s.trim()).filter(Boolean) : [],
        priority: Number(this.selectedTask.priority) || 0
      }
      try {
        const res = await fetch(`http://localhost:8000/todos/${this.selectedTask.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        if (!res.ok) throw new Error(await res.text())
        const updated = await res.json()

        this.todos = this.todos.map(t => t.id === updated.id ? updated : t)
        this.weekTodos = this.weekTodos.map(t => t.id === updated.id ? updated : t)
        this.markTodosForWeek()
        this.selectedTask = null
      } catch (err) {
        console.error(err)
        alert('保存失败：' + err.message)
      }
    },

    async addNL() {
      if (!this.nlText.trim()) return alert('请输入自然语言描述')
      this.loading = true
      try {
        const res = await fetch('http://localhost:8000/todos/nl', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: this.nlText, now: this.currentTimeISO })
        })
        if (!res.ok) {
          const txt = await res.text()
          throw new Error(txt || '后端返回错误')
        }
        const body = await res.json()

        if (body && (body.deleted || body.count)) {
          const ids = (body.deleted || []).map(d => d.id)
          if (ids.length) {
            this.todos = this.todos.filter(t => !ids.includes(t.id))
            this.weekTodos = this.weekTodos.filter(t => !ids.includes(t.id))
            this.markTodosForWeek()
          }
          alert(`已删除 ${body.count || 0} 项`)
        } else if (body && body.id) {

          this.todos.unshift(body)
        } else {

          this.todos.unshift(body)
        }
        this.nlText = ''
      } catch (err) {
        console.error(err)
        alert('添加失败：' + err.message)
      } finally {
        this.loading = false
      }
    },

    async deleteTodo(id) {
      const ok = confirm('确定删除这个待办吗？')
      if (!ok) return
      try {
        const res = await fetch(`http://localhost:8000/todos/${id}`, { method: 'DELETE' })
        if (res.status !== 204) {
          const txt = await res.text()
          throw new Error(txt || `删除失败，状态码 ${res.status}`)
        }
        this.todos = this.todos.filter(t => t.id !== id)
        this.weekTodos = this.weekTodos.filter(t => t.id !== id)
        this.markTodosForWeek()
      } catch (err) {
        console.error(err)
        alert('删除失败：' + err.message)
      }
    }
    ,
    toggleTodoList() {
      this.showTodoList = !this.showTodoList
    }
  }
  ,
  computed: {
    weekLabel() {
      if (!this.weekDates || this.weekDates.length === 0) return ''
      const a = this.weekDates[0]
      const b = this.weekDates[this.weekDates.length - 1]
      return `${a} — ${b}`
    }
  }
}).mount('body')

var apiRoot = 'https://eventpartner.moveon.org/'

window.onload = function () {

  Vue.component('submit-button', {
    props: ['isDisabled', 'prompt'],
    template: `<button
      type="button"
      class="btn pl-5 pr-5 pt-2 pb-2"
      v-bind:disabled="isDisabled"
      @click="$emit('submit-button-click')"
    >{{ prompt }}</button>`
  })

  Vue.component('error-message', {
    props: ['isOn', 'error'],
    template: `<div class="mt-3" v-if="isOn">
      <p class="message message-error">{{ error }}</p>
    </div>`
  })

  var app = new Vue({
    el: '#export-form',
    data: {
      key: '',
      error: false
    },
    methods: {
      formSubmit: function() {
        var vueApp = this
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            if (this.readyState != 4) return
            if (this.status == 200) {
                response = JSON.parse(this.responseText)
                if (response.valid) {
                  vueApp.error = false
                  vueApp.$refs.form.submit()
                }
                else {
                  vueApp.error = true
                }
            }
            else {
              vueApp.error = true
            }
        }
        xhr.open("POST", apiRoot + 'validate/', true)
        xhr.setRequestHeader('Content-Type', 'application/json')
        xhr.send(JSON.stringify({'KEY': this.key}))
      }
    }
  })

}

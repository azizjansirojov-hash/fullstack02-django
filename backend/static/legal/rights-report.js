(function () {
  var form = document.getElementById('rights-report-form')
  var statusEl = document.getElementById('rights-report-status')
  if (!form || !statusEl) return
  form.addEventListener('submit', function (e) {
    e.preventDefault()
    var csrf = form.querySelector('[name=csrfmiddlewaretoken]')
    var data = {
      name: form.name.value,
      email: form.email.value,
      book_ref: form.book_ref.value,
      message: form.message.value,
    }
    fetch('/api/rights-report/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf ? csrf.value : '',
      },
      body: JSON.stringify(data),
    })
      .then(function (r) {
        return r.json().then(function (j) {
          statusEl.textContent = j.detail || (r.ok ? 'OK' : 'Error')
        })
      })
      .catch(function () {
        statusEl.textContent = 'Network error'
      })
  })
})()

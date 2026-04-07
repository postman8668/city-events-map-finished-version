// Валидация формы с подсветкой ошибок
function validateForm(formElement) {
    let isValid = true;
    let firstInvalidField = null;
    
    // Удаляем предыдущие классы ошибок
    formElement.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    
    // Проверяем все required поля
    formElement.querySelectorAll('[required]').forEach(field => {
        if (!field.value || field.value.trim() === '') {
            field.classList.add('is-invalid');
            isValid = false;
            if (!firstInvalidField) firstInvalidField = field;
        }
    });
    
    // Прокручиваем к первому невалидному полю
    if (firstInvalidField) {
        firstInvalidField.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstInvalidField.focus();
    }
    
    return isValid;
}

// Добавляем обработчик на форму
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    }
});

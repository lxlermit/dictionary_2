from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory

import os
import json
import random
from datetime import datetime

app = Flask(__name__, template_folder='../html', static_folder='html/audio', static_url_path='/audio')
app.secret_key = 'your_secret_key'


# Загрузка данных пользователей
def load_user_data(username):
    if username == 'noname':
        filepath = os.path.join('users', 'noname.json')
    else:
        filepath = os.path.join('users', f'{username}.json')

    if not os.path.exists(filepath):
        return None  # Файл пользователя не существует

    with open(filepath, 'r', encoding='utf-8') as file:
        return json.load(file)


# Сохранение данных пользователей
def save_user_data(username, data):
    filepath = os.path.join('users', f'{username}.json')
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


# Выбор случайного слова и его переводов
def get_random_word_and_translations(user_data):
    words = list(user_data['dict'].keys())
    if not words:
        return None, []  # Если словарь пуст

    random_word = random.choice(words)
    correct_translation = user_data['dict'][random_word][0]

    # Собираем все возможные переводы
    all_translations = [item[0] for item in user_data['dict'].values()]
    all_translations.remove(correct_translation)  # Убираем правильный перевод

    # Выбираем 4 случайных неправильных перевода
    wrong_translations = random.sample(all_translations, min(4, len(all_translations)))

    # Создаем список из 5 переводов (1 правильный + 4 неправильных)
    translations = wrong_translations + [correct_translation]
    random.shuffle(translations)  # Перемешиваем

    return random_word, translations


@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_data = load_user_data(username)

    # Если файл пользователя не существует, очищаем сессию и перенаправляем на логин
    if user_data is None:
        session.pop('username', None)
        return redirect(url_for('login'))

    random_word, translations = get_random_word_and_translations(user_data)
    if not random_word:
        return "Словарь пуст. Добавьте слова в разделе редактирования."

    # Получаем текущую дату
    today = datetime.now().strftime('%Y-%m-%d')

    # Инициализируем daily_activity для сегодняшней даты, если её нет
    if today not in user_data['daily_activity']:
        user_data['daily_activity'][today] = [0, 0, 0]  # [правильные, неправильные, прогресс]

    # Получаем прогресс
    correct, incorrect, progress = user_data['daily_activity'][today]
    daily_goal = user_data.get('daily_goal', 30)
    progress_percentage = (progress / daily_goal) * 100 if daily_goal > 0 else 0

    # Проверяем, достигнута ли цель
    celebration = progress >= daily_goal

    # Передаем результат проверки, если он есть
    result = session.pop('result', None)

    return render_template(
        'index.html',
        username=username,
        random_word=random_word,
        translations=translations,
        result=result,
        progress=progress,
        daily_goal=daily_goal,
        progress_percentage=progress_percentage,
        celebration=celebration
    )


@app.route('/check_answer', methods=['POST'])
def check_answer():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_data = load_user_data(username)

    # Если файл пользователя не существует, очищаем сессию и перенаправляем на логин
    if user_data is None:
        session.pop('username', None)
        return redirect(url_for('login'))

    selected_translation = request.form['translation']
    random_word = request.form['word']

    correct_translation = user_data['dict'][random_word][0]

    # Находим слово, соответствующее выбранному переводу
    selected_word = None
    for word, translation_data in user_data['dict'].items():
        if translation_data[0] == selected_translation:
            selected_word = word
            break

    # Получаем текущую дату
    today = datetime.now().strftime('%Y-%m-%d')

    # Инициализируем daily_activity для сегодняшней даты, если её нет
    if today not in user_data['daily_activity']:
        user_data['daily_activity'][today] = [0, 0, 0]  # [правильные, неправильные, прогресс]

    # Обновляем статистику для загаданного слова
    if selected_translation == correct_translation:
        # Увеличиваем количество правильных ответов для загаданного слова
        user_data['dict'][random_word][1] += 1
        # Увеличиваем количество правильных ответов за день
        user_data['daily_activity'][today][0] += 1
    else:
        # Увеличиваем количество ошибок для загаданного слова
        user_data['dict'][random_word][2] += 1
        # Увеличиваем количество ошибок за день
        user_data['daily_activity'][today][1] += 1

    # Обновляем статистику для выбранного перевода (если это другое слово)
    if selected_word and selected_word != random_word:
        if selected_translation == correct_translation:
            # Увеличиваем количество правильных ответов для выбранного слова
            user_data['dict'][selected_word][1] += 1
        else:
            # Увеличиваем количество ошибок для выбранного слова
            user_data['dict'][selected_word][2] += 1

    # Пересчитываем прогресс
    correct, incorrect, _ = user_data['daily_activity'][today]
    progress = max(0, correct - incorrect)
    user_data['daily_activity'][today][2] = progress

    # Сохраняем данные
    save_user_data(username, user_data)

    # Проверяем ответ
    if selected_translation == correct_translation:
        result = {
            'correct': True,
            'word': random_word,
            'correct_answer': correct_translation
        }
    else:
        result = {
            'correct': False,
            'word': random_word,
            'correct_answer': correct_translation,
            'selected_translation': selected_translation,
            'selected_word': selected_word
        }

    # Сохраняем результат в сессии для отображения на странице
    session['result'] = result

    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Проверяем, существует ли файл registration.json
        if not os.path.exists('registration.json'):
            return "Пользователь не найден."

        with open('registration.json', 'r', encoding='utf-8') as file:
            users = json.load(file)

        if username in users and users[username] == password:
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return "Неверный логин или пароль."

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Проверяем, существует ли файл registration.json
        if not os.path.exists('registration.json'):
            with open('registration.json', 'w', encoding='utf-8') as file:
                json.dump({}, file, ensure_ascii=False, indent=4)

        with open('registration.json', 'r', encoding='utf-8') as file:
            users = json.load(file)

        if username in users:
            return "Имя пользователя уже занято."

        users[username] = password

        with open('registration.json', 'w', encoding='utf-8') as file:
            json.dump(users, file, ensure_ascii=False, indent=4)

        # Загружаем данные из noname.json
        noname_file = os.path.join('users', 'noname.json')
        with open(noname_file, 'r', encoding='utf-8') as file:
            noname_data = json.load(file)

        # Создаем файл нового пользователя с данными из noname.json
        new_user_file = os.path.join('users', f'{username}.json')
        with open(new_user_file, 'w', encoding='utf-8') as file:
            json.dump(noname_data, file, ensure_ascii=False, indent=4)

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/static/<path:filename>')
def static_files(filename):
    return app.send_static_file(filename)


@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(app.static_folder, filename, mimetype='audio/mpeg')



if __name__ == "__main__":
    app.run(debug=True)
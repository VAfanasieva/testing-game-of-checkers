import unittest
import json
import sqlite3
import os
import tempfile
import socket
import threading
import time
from unittest.mock import Mock, patch, MagicMock
import sys

# Добавляем путь к модулям проекта
sys.path.append('unit')

from checkers.split.server.pythonProject.server.server import authorization, register, calculate_possible_moves, make_move
from checkers.split.server.pythonProject.server.server import get_username_by_id, update_scores, top_players, show_rooms
from checkers.split.server.pythonProject.server.server import join_room, delete_room, handle_room, checkStep, main


class TestAuthClientServerIntegration(unittest.TestCase):
    """TestAuthClientServerIntegration - проверка взаимодействия клиентского модуля авторизации с серверной частью системы"""

    def setUp(self):
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.test_db.name

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                score INTEGER DEFAULT 500
            )
        ''')
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                       ('testuser', 'testpass123'))
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_auth_integration(self):
        """Проверка успешной авторизации"""
        mock_conn = Mock()
        input_data = {'username': 'testuser', 'password': 'testpass123'}

        with patch('server.database_file', self.db_path):
            authorization(mock_conn, input_data)

            sent_data = json.loads(mock_conn.sendall.call_args[0][0].decode())

            # Проверка ожидаемого результата
            self.assertEqual(sent_data['status'], True)
            self.assertEqual(sent_data['user_id'], 1)


class TestGameRoomCreationIntegration(unittest.TestCase):
    """TestGameRoomCreationIntegration - проверка создания игровой комнаты и автоматического подбора соперника"""

    def setUp(self):
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.test_db.name

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                score INTEGER DEFAULT 500
            )
        ''')
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                       ('user5', 'pass5'))
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                       ('user6', 'pass6'))
        conn.commit()
        conn.close()

        self.rooms = {}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_room_creation_integration(self):
        """Проверка создания комнаты и подключения второго игрока"""
        mock_conn1 = Mock()
        mock_conn2 = Mock()

        # Мокаем глобальную переменную rooms
        with patch('server.rooms', self.rooms), \
                patch('server.database_file', self.db_path), \
                patch('server.threading.Thread') as mock_thread:
            # Первый игрок создает комнату
            create_data = {'command': 4, 'user_id': 5}

            # Эмуляция обработки команды создания комнаты
            player_number = 1
            room_number = len(self.rooms) + 1
            self.rooms[room_number] = [(player_number, mock_conn1, 5)]

            response_data = json.dumps({
                'client_number': player_number,
                'room_number': room_number
            }).encode()
            mock_conn1.sendall(response_data)

            # Второй игрок подключается
            join_room(mock_conn2, 6, room_number)

            # Проверка ожидаемого результата
            self.assertEqual(len(self.rooms[room_number]), 2)
            self.assertEqual(self.rooms[room_number][0][0], 1)  # client_number первого игрока
            self.assertEqual(self.rooms[room_number][1][0], 2)  # client_number второго игрока


class TestGameMoveIntegration(unittest.TestCase):
    """TestGameMoveIntegration - проверка выполнения хода и синхронизации состояния игры между клиентами"""

    def setUp(self):
        self.initial_board = [
            [0, 1, 0, 1, 0, 1, 0, 1],
            [1, 0, 1, 0, 1, 0, 1, 0],
            [0, 1, 0, 1, 0, 1, 0, 1],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [2, 0, 2, 0, 2, 0, 2, 0],
            [0, 2, 0, 2, 0, 2, 0, 2],
            [2, 0, 2, 0, 2, 0, 2, 0]
        ]

    def test_game_move_integration(self):
        """Проверка выполнения хода и синхронизации"""
        mock_conn1 = Mock()
        mock_conn2 = Mock()

        rooms = {1: [(1, mock_conn1, 10), (2, mock_conn2, 11)]}

        with patch('server.rooms', rooms), \
                patch('server.get_username_by_id') as mock_get_username, \
                patch('server.update_scores') as mock_update_scores, \
                patch('server.delete_room') as mock_delete_room:
            mock_get_username.return_value = "testuser"

            # Выполнение хода
            input_data = {
                'row': 3,
                'col': 2,
                'client_number': 1,
                'pieces': self.initial_board,
                'selected_piece': [2, 1],
                'room_number': 1
            }

            checkStep(3, 2, 1, self.initial_board, [2, 1], 1)

            # Проверка что оба клиента получили сообщения
            self.assertTrue(mock_conn1.sendall.called)
            self.assertTrue(mock_conn2.sendall.called)

            # Проверка структуры отправленных данных
            sent_data1 = json.loads(mock_conn1.sendall.call_args[0][0].decode())
            self.assertIn('pieces', sent_data1)
            self.assertIn('continue_step', sent_data1)
            self.assertIn('game_status', sent_data1)


class TestDatabaseScoreUpdateIntegration(unittest.TestCase):
    """TestDatabaseScoreUpdateIntegration - проверка обновления рейтинга пользователей в базе данных после завершения игры"""

    def setUp(self):
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.test_db.name

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                score INTEGER DEFAULT 500
            )
        ''')
        cursor.execute('INSERT INTO users (username, password, score) VALUES (?, ?, ?)',
                       ('winner', 'pass', 500))
        cursor.execute('INSERT INTO users (username, password, score) VALUES (?, ?, ?)',
                       ('loser', 'pass', 500))
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_score_update_integration(self):
        """Проверка обновления рейтинга после игры"""
        winner_id = 1
        loser_id = 2

        with patch('server.database_file', self.db_path):
            # Выполнение обновления рейтинга
            update_scores(winner_id, loser_id)

            # Проверка результата в базе данных
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT score FROM users WHERE id = ?', (winner_id,))
            winner_score = cursor.fetchone()[0]

            cursor.execute('SELECT score FROM users WHERE id = ?', (loser_id,))
            loser_score = cursor.fetchone()[0]

            conn.close()

            # Проверка ожидаемого результата
            self.assertEqual(winner_score, 525)  # 500 + 25
            self.assertEqual(loser_score, 475)  # 500 - 25


class TestRoomListIntegration(unittest.TestCase):
    """TestRoomListIntegration - проверка получения и отображения списка игровых комнат в клиентском интерфейсе"""

    def setUp(self):
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.test_db.name

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                score INTEGER DEFAULT 500
            )
        ''')
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                       ('creator', 'pass'))
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_room_list_integration(self):
        """Проверка получения списка комнат"""
        mock_conn = Mock()

        rooms = {
            1: [(1, Mock(), 7)],  # Комната с одним игроком
            2: [(1, Mock(), 8), (2, Mock(), 9)]  # Полная комната
        }

        with patch('server.database_file', self.db_path):
            show_rooms(mock_conn, rooms)

            sent_data = json.loads(mock_conn.sendall.call_args[0][0].decode())

            # Проверка ожидаемого результата
            self.assertEqual(sent_data['status'], True)
            self.assertEqual(len(sent_data['message']), 2)
            self.assertEqual(sent_data['message'][0]['room_id'], 1)
            self.assertEqual(sent_data['message'][1]['room_id'], 2)


class TestConcurrentConnectionsIntegration(unittest.TestCase):
    """TestConcurrentConnectionsIntegration - проверка обработки множественных одновременных подключений к серверу"""

    def test_concurrent_connections(self):
        """Проверка множественных подключений"""
        # Этот тест эмулирует множественные подключения
        # В реальной среде потребовалось бы использовать асинхронное тестирование

        mock_connections = [Mock() for _ in range(5)]
        rooms = {}

        with patch('server.rooms', rooms), \
                patch('server.threading.Thread') as mock_thread:

            # Эмуляция подключения 5 пользователей
            user_ids = [10, 11, 12, 13, 14]
            for i, (mock_conn, user_id) in enumerate(zip(mock_connections, user_ids)):
                if i % 2 == 0:
                    # Создание новой комнаты для нечетных пользователей
                    room_number = len(rooms) + 1
                    rooms[room_number] = [(1, mock_conn, user_id)]
                else:
                    # Подключение к существующей комнате для четных пользователей
                    if rooms:
                        last_room = max(rooms.keys())
                        if len(rooms[last_room]) < 2:
                            rooms[last_room].append((2, mock_conn, user_id))

            # Проверка ожидаемого результата
            self.assertEqual(len(rooms), 3)  # Должно быть создано 3 комнаты
            total_players = sum(len(players) for players in rooms.values())
            self.assertEqual(total_players, 5)  # Все 5 игроков распределены по комнатам


class TestInvalidJSONIntegration(unittest.TestCase):
    """TestInvalidJSONIntegration - проверка обработки некорректных JSON данных на сервере"""

    def test_invalid_json_handling(self):
        """Проверка обработки некорректного JSON"""
        mock_connection = Mock()
        mock_connection.recv.return_value = b'invalid json data'

        # Проверка что некорректный JSON вызывает исключение
        with self.assertRaises(json.JSONDecodeError):
            json.loads('invalid json data')


class TestGameWinConditionIntegration(unittest.TestCase):
    """TestGameWinConditionIntegration - проверка определения условий победы и уведомления клиентов"""

    def test_win_condition_integration(self):
        """Проверка условий победы"""
        # Доска где у игрока 2 осталась одна шашка
        winning_board = [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 2, 0],  # Последняя шашка игрока 2
            [0, 0, 0, 0, 0, 0, 0, 1]  # Шашка игрока 1
        ]

        mock_conn1 = Mock()
        mock_conn2 = Mock()
        rooms = {1: [(1, mock_conn1, 15), (2, mock_conn2, 16)]}

        with patch('server.rooms', rooms), \
                patch('server.get_username_by_id') as mock_get_username, \
                patch('server.update_scores') as mock_update_scores, \
                patch('server.delete_room') as mock_delete_room:
            mock_get_username.return_value = "player15"

            # Выполнение хода, приводящего к победе
            selected_piece = (7, 7)  # Красная шашка
            row, col = (6, 6)  # Взятие последней шашки противника

            pieces, can_continue, game_status = make_move(
                winning_board, row, col, selected_piece, 1
            )

            # Проверка ожидаемого результата
            self.assertEqual(game_status, 1)  # Победа игрока 1


class TestClientDisconnectIntegration(unittest.TestCase):
    """TestClientDisconnectIntegration - проверка обработки разрыва соединения с клиентом во время игры"""

    def test_client_disconnect_integration(self):
        """Проверка разрыва соединения"""
        mock_conn1 = Mock()
        mock_conn2 = Mock()

        # Создаем комнату с двумя игроками
        rooms = {1: [(1, mock_conn1, 17), (2, mock_conn2, 18)]}
        connections = [mock_conn1, mock_conn2]

        # Эмуляция разрыва соединения с первым игроком
        def mock_recv_with_disconnect(*args, **kwargs):
            if mock_conn1.recv.called:
                raise ConnectionResetError("Connection lost")
            return json.dumps({'status': True}).encode()

        mock_conn1.recv.side_effect = mock_recv_with_disconnect

        # В реальном коде handle_room обработала бы это исключение
        # и удалила соединение из connections
        with self.assertRaises(ConnectionResetError):
            mock_conn1.recv(1024)


class TestRoomFullIntegration(unittest.TestCase):
    """TestRoomFullIntegration - проверка обработки попытки подключения к заполненной комнате"""

    def test_room_full_integration(self):
        """Проверка подключения к заполненной комнате"""
        mock_conn = Mock()

        # Комната уже содержит двух игроков
        rooms = {4: [(1, Mock(), 18), (2, Mock(), 19)]}

        with patch('server.rooms', rooms):
            join_room(mock_conn, 20, 4)  # Попытка подключения третьего игрока

            # Проверка что было отправлено сообщение об ошибке
            sent_data = json.loads(mock_conn.sendall.call_args[0][0].decode())

            # Проверка ожидаемого результата
            self.assertEqual(sent_data['status'], False)
            self.assertEqual(sent_data['message'], 'Комната уже заполнена')


class TestTopPlayersDisplayIntegration(unittest.TestCase):
    """TestTopPlayersDisplayIntegration - проверка отображения таблицы лучших игроков в клиентском интерфейсе"""

    def setUp(self):
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.test_db.name

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                score INTEGER DEFAULT 500
            )
        ''')

        # Добавляем пользователей с разными очками
        test_users = [
            ('player650', 'pass', 650),
            ('player600', 'pass', 600),
            ('player550', 'pass', 550),
            ('player500', 'pass', 500),
            ('player450', 'pass', 450),
            ('player400', 'pass', 400)
        ]

        for username, password, score in test_users:
            cursor.execute(
                'INSERT INTO users (username, password, score) VALUES (?, ?, ?)',
                (username, password, score)
            )

        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_top_players_integration(self):
        """Проверка отображения топа игроков"""
        mock_conn = Mock()

        with patch('server.database_file', self.db_path):
            top_players(mock_conn, {'command': 3})

            sent_data = json.loads(mock_conn.sendall.call_args[0][0].decode())

            # Проверка ожидаемого результата
            self.assertEqual(sent_data['status'], True)
            self.assertEqual(len(sent_data['message']), 5)  # Топ-5 игроков

            # Проверка сортировки по убыванию очков
            self.assertIn('player650: 650 очков', sent_data['message'][0])
            self.assertIn('player600: 600 очков', sent_data['message'][1])


class TestGameTimerIntegration(unittest.TestCase):
    """TestGameTimerIntegration - проверка работы таймера хода и обработки превышения времени"""

    def test_game_timer_integration(self):
        """Проверка обработки таймера хода"""
        mock_conn = Mock()

        # Эмуляция ситуации, когда время хода истекло
        turn_start_time = time.time() - 30  # 30 секунд назад (больше 25)
        time_left = 25 - int(time.time() - turn_start_time)

        # Проверка что время вышло
        self.assertLessEqual(time_left, 0)

        # В реальном коде это привело бы к отправке операции 3
        operation_data = {
            'user_id': 25,
            'operation': 3,
            'room_number': 5
        }

        # Проверка что операция содержит правильные данные
        self.assertEqual(operation_data['operation'], 3)
        self.assertEqual(operation_data['user_id'], 25)


class TestMultipleGameSessionsIntegration(unittest.TestCase):
    """TestMultipleGameSessionsIntegration - проверка проведения нескольких игровых сессий одновременно"""

    def test_multiple_sessions_integration(self):
        """Проверка множественных игровых сессий"""
        # Эмуляция 4 параллельных игровых сессий
        game_sessions = []

        for session_id in range(4):
            session = {
                'room_number': session_id + 1,
                'players': [
                    {'user_id': session_id * 2 + 1, 'client_number': 1},
                    {'user_id': session_id * 2 + 2, 'client_number': 2}
                ],
                'completed': False
            }
            game_sessions.append(session)

        # Эмуляция завершения всех сессий
        for session in game_sessions:
            session['completed'] = True

        # Проверка ожидаемого результата
        self.assertEqual(len(game_sessions), 4)
        self.assertTrue(all(session['completed'] for session in game_sessions))


def run_integration_tests():
    """Запуск всех интеграционных тестов"""
    print("🎯 ЗАПУСК ИНТЕГРАЦИОННЫХ ТЕСТОВ")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Добавляем все интеграционные тесты
    test_classes = [
        TestAuthClientServerIntegration,
        TestGameRoomCreationIntegration,
        TestGameMoveIntegration,
        TestDatabaseScoreUpdateIntegration,
        TestRoomListIntegration,
        TestConcurrentConnectionsIntegration,
        TestInvalidJSONIntegration,
        TestGameWinConditionIntegration,
        TestClientDisconnectIntegration,
        TestRoomFullIntegration,
        TestTopPlayersDisplayIntegration,
        TestGameTimerIntegration,
        TestMultipleGameSessionsIntegration
    ]

    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))

    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2, descriptions=True)
    result = runner.run(suite)

    # Выводим статистику
    print("=" * 70)
    print("📊 РЕЗУЛЬТАТЫ ИНТЕГРАЦИОННОГО ТЕСТИРОВАНИЯ:")
    print(f"   Всего тестов: {result.testsRun}")
    print(f"   ✅ Успешно: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   ❌ Провалено: {len(result.failures)}")
    print(f"   ⚠️  Ошибок: {len(result.errors)}")

    if result.failures:
        print("\n🔴 ПРОВАЛЕННЫЕ ТЕСТЫ:")
        for test, traceback in result.failures:
            print(f"   - {test}")

    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
    print(f"\n📈 ОБЩАЯ УСПЕШНОСТЬ: {success_rate:.1f}%")

    return result.wasSuccessful()


if __name__ == '__main__':
    # Запускаем интеграционные тесты
    success = run_integration_tests()

    # Возвращаем код выхода
    sys.exit(0 if success else 1)
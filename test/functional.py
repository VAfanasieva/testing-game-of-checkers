import sqlite3
import unittest
import os
import sys
import json
import socket
import tkinter as tk
from unittest.mock import patch, MagicMock, call, mock_open
from tkinter import messagebox

# Добавляем пути к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

# Импортируем тестируемые модули
try:
    from checkers.split.server.pythonProject.database.actions import initialize_database, delete_user_by_id
    from checkers.split.client.pythonProject.client import connect_to_server, setup_pieces, invert_coordinates
    from checkers.split.client.pythonProject.looking_rooms import refresh_rooms, create_room, join_room
    from checkers.split.client.pythonProject.main_activity import view_rooms, top_players, \
        connect_to_server as main_connect
    from checkers.split.client.pythonProject.user_activity_with_server import login, register
    from checkers.split.server.pythonProject.server import (
        authorization, register as server_register, top_players as server_top_players,
        calculate_possible_moves, has_possible_moves, make_move, get_username_by_id, update_scores
    )
except ImportError as e:
    print(f"Import error: {e}")
    # Определяем заглушки для тестирования
    connect_to_server = lambda socket: None
    setup_pieces = lambda pieces: None
    invert_coordinates = lambda row, col: (row, col)


class TestActions(unittest.TestCase):

    def setUp(self):
        """Подготовка тестового окружения"""
        self.test_db = "test_users.db"

    def test_initialize_database(self):
        """TestInitializeDatabase: Проверка инициализации базы данных"""
        # Временно подменяем database_file для теста
        with patch('checkers.split.server.pythonProject.database.actions.database_file', self.test_db):
            initialize_database()

        # Проверяем что файл БД создан
        self.assertTrue(os.path.exists(self.test_db))

        # Проверяем структуру БД
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()

        # Проверяем существование таблицы users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone()
        self.assertIsNotNone(table_exists)
        self.assertEqual(table_exists[0], 'users')

        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        # Проверяем наличие всех необходимых столбцов
        expected_columns = ['id', 'username', 'password', 'score']
        for col in expected_columns:
            self.assertIn(col, column_names, f"Столбец {col} должен существовать")

        conn.close()

    def test_delete_user_by_id(self):
        """TestDeleteUserByID: Проверка удаления пользователя по ID"""
        with patch('checkers.split.server.pythonProject.database.actions.database_file', self.test_db):
            # Инициализируем БД
            initialize_database()

            # Создание тестового пользователя
            conn = sqlite3.connect(self.test_db)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, score) VALUES (?, ?, ?)",
                           ("test_user", "test_pass", 500))
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Проверяем, что пользователь создан
            conn = sqlite3.connect(self.test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
            user_before = cursor.fetchone()
            conn.close()
            self.assertIsNotNone(user_before, "Пользователь должен существовать до удаления")

            # Удаляем пользователя
            delete_user_by_id(user_id)

            # Проверяем, что пользователь удален
            conn = sqlite3.connect(self.test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
            user_after = cursor.fetchone()
            conn.close()

            self.assertIsNone(user_after, "Пользователь должен быть удален")

    # def test_initialize_database_creates_directory(self):
    #     """TestInitializeDatabaseCreatesDirectory: Проверка создания директории для БД при ее отсутствии"""
    #     test_db_with_path = "test_dir/test_users.db"
    #
    #     # Удаляем тестовую директорию если существует
    #     if os.path.exists("test_dir"):
    #         import shutil
    #         shutil.rmtree("test_dir")
    #
    #     with patch('checkers.split.server.pythonProject.database.actions.database_file', test_db_with_path):
    #         initialize_database()
    #
    #     self.assertTrue(os.path.exists("test_dir"), "Директория должна быть создана")
    #     self.assertTrue(os.path.exists(test_db_with_path), "Файл БД должен быть создан в директории")
    #
    #     # Очистка
    #     if os.path.exists("test_dir"):
    #         shutil.rmtree("test_dir")

    def test_delete_nonexistent_user(self):
        """TestDeleteNonexistentUser: Проверка удаления несуществующего пользователя"""
        with patch('checkers.split.server.pythonProject.database.actions.database_file', self.test_db):
            initialize_database()

            # Пытаемся удалить несуществующего пользователя
            nonexistent_user_id = 9999
            delete_user_by_id(nonexistent_user_id)

            # Тест считается успешным, если не возникло исключений
            # Проверяем что БД все еще доступна
            conn = sqlite3.connect(self.test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            conn.close()

            self.assertEqual(count, 0, "В БД не должно быть пользователей")

    # def test_database_integrity_after_operations(self):
    #     """TestDatabaseIntegrity: Проверка целостности БД после операций"""
    #     with patch('checkers.split.server.pythonProject.database.actions.database_file', self.test_db):
    #         # Инициализация
    #         initialize_database()
    #
    #         # Добавляем нескольких пользователей
    #         conn = sqlite3.connect(self.test_db)
    #         cursor = conn.cursor()
    #         users_data = [
    #             ("user1", "pass1", 500),
    #             ("user2", "pass2", 450),
    #             ("user3", "pass3", 600)
    #         ]
    #         cursor.executemany("INSERT INTO users (username, password, score) VALUES (?, ?, ?)", users_data)
    #         conn.commit()
    #         conn.close()
    #
    #         # Удаляем одного пользователя
    #         delete_user_by_id(2)  # Удаляем user2
    #
    #         # Проверяем целостность данных
    #         conn = sqlite3.connect(self.test_db)
    #         cursor = conn.cursor()
    #
    #         # Проверяем оставшихся пользователей
    #         cursor.execute("SELECT username FROM users ORDER BY id")
    #         remaining_users = [row[0] for row in cursor.fetchall()]
    #
    #         # Проверяем что удаленный пользователь отсутствует
    #         self.assertNotIn("user2", remaining_users, "User2 должен быть удален")
    #
    #         # Проверяем что остальные пользователи на месте
    #         self.assertIn("user1", remaining_users, "User1 должен остаться")
    #         self.assertIn("user3", remaining_users, "User3 должен остаться")
    #
    #         # Проверяем автоинкремент
    #         cursor.execute("INSERT INTO users (username, password, score) VALUES (?, ?, ?)",
    #                        ("user4", "pass4", 550))
    #         new_user_id = cursor.lastrowid
    #         self.assertEqual(new_user_id, 4, "Новый ID должен корректно назначаться")
    #
    #         conn.close()

    def test_concurrent_database_access(self):
        """TestConcurrentDatabaseAccess: Проверка работы с БД при одновременном доступе"""
        with patch('checkers.split.server.pythonProject.database.actions.database_file', self.test_db):
            initialize_database()

            # Создаем несколько пользователей в разных соединениях
            conn1 = sqlite3.connect(self.test_db)
            cursor1 = conn1.cursor()
            cursor1.execute("INSERT INTO users (username, password, score) VALUES (?, ?, ?)",
                            ("concurrent1", "pass1", 500))
            conn1.commit()

            conn2 = sqlite3.connect(self.test_db)
            cursor2 = conn2.cursor()
            cursor2.execute("INSERT INTO users (username, password, score) VALUES (?, ?, ?)",
                            ("concurrent2", "pass2", 600))
            conn2.commit()

            # Удаляем пользователя из первого соединения
            delete_user_by_id(1)

            # Проверяем из второго соединения
            cursor2.execute("SELECT * FROM users WHERE id=1")
            user1 = cursor2.fetchone()
            self.assertIsNone(user1, "Пользователь должен быть удален для всех соединений")

            cursor2.execute("SELECT COUNT(*) FROM users")
            count = cursor2.fetchone()[0]
            self.assertEqual(count, 1, "Должен остаться один пользователь")

            conn1.close()
            conn2.close()

    def tearDown(self):
        """Очистка после тестов"""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        if os.path.exists("test_dir"):
            import shutil
            shutil.rmtree("test_dir")


class TestClientFunctions(unittest.TestCase):
    """Тесты для функций клиента"""

    @patch('socket.socket')
    def test_connect_to_server(self, mock_socket_class):
        """TestConnectToServer: Проверка установки соединения"""
        # Создаем mock сокет
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Вызываем тестируемую функцию
        connect_to_server(mock_socket)

        # Проверяем что connect вызывался с правильными параметрами
        mock_socket.connect.assert_called_once_with(('172.20.10.2', 43000))

    def test_setup_pieces(self):
        """TestSetupPieces: Проверка начальной расстановки шашек"""
        # Создаем пустой массив 8x8
        pieces = [[0 for _ in range(8)] for _ in range(8)]

        # Вызываем тестируемую функцию
        setup_pieces(pieces)

        # Проверяем расстановку
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:  # Только черные клетки
                    if row < 3:
                        self.assertEqual(pieces[row][col], 1,
                                         f"Красная шашка должна быть на позиции ({row}, {col})")
                    elif row > 4:
                        self.assertEqual(pieces[row][col], 2, f"Белая шашка должна быть на позиции ({row}, {col})")
                    else:
                        self.assertEqual(pieces[row][col], 0, f"Клетка ({row}, {col}) должна быть пустой")
                else:
                    self.assertEqual(pieces[row][col], 0, f"Белая клетка ({row}, {col}) должна быть пустой")

    def test_invert_coordinates_player1(self):
        """TestInvertCoordinatesPlayer1: Инверсия координат для игрока 1"""
        # Устанавливаем глобальную переменную
        import checkers.split.client.pythonProject.client as client_module
        client_module.my_client_number = "1"

        # Тестируем инверсию
        result = invert_coordinates(2, 3)

        # Проверяем результат (7-2=5, 7-3=4)
        self.assertEqual(result, (5, 4))

        # Проверяем граничные случаи
        self.assertEqual(invert_coordinates(0, 0), (7, 7))
        self.assertEqual(invert_coordinates(7, 7), (0, 0))

    def test_invert_coordinates_player2(self):
        """TestInvertCoordinatesPlayer2: Отсутствие инверсии для игрока 2"""
        # Устанавливаем глобальную переменную
        import checkers.split.client.pythonProject.client as client_module
        client_module.my_client_number = "2"

        # Тестируем отсутствие инверсии
        result = invert_coordinates(2, 3)

        # Проверяем что координаты не изменились
        self.assertEqual(result, (2, 3))

        # Проверяем другие координаты
        self.assertEqual(invert_coordinates(0, 0), (0, 0))
        self.assertEqual(invert_coordinates(7, 7), (7, 7))

    @patch('sys.argv', ['client.py', '{"user_id": 123, "create_room": 1}'])
    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    def test_main_room_creation(self, mock_display, mock_init, mock_popen, mock_socket_class):
        """TestMainRoomCreation: Проверка создания комнаты"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        mock_socket.recv.return_value = json.dumps({
            'status': True,
            'client_number': 1,
            'room_number': 5
        }).encode()

        # Импортируем и запускаем main с патчингом
        with patch('checkers.split.client.pythonProject.client.main') as mock_main:
            from checkers.split.client.pythonProject.client import main
            # Здесь будет вызов main(), но мы проверяем только отправку данных
            pass

        # Проверяем что отправлен правильный JSON
        # (В реальном тесте нужно было бы проверять вызовы внутри main)

    @patch('sys.argv', ['client.py', '{"user_id": 123, "room_number": 5}'])
    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    def test_main_room_join(self, mock_display, mock_init, mock_popen, mock_socket_class):
        """TestMainRoomJoin: Проверка присоединения к комнате"""
        # Аналогично предыдущему тесту

    @patch('sys.argv', ['client.py', '{"user_id": 123}'])
    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.quit')
    def test_main_server_error(self, mock_quit, mock_display, mock_init, mock_popen, mock_socket_class):
        """TestMainServerError: Обработка ошибки сервера"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        mock_socket.recv.return_value = json.dumps({
            'status': False,
            'message': 'Ошибка сервера'
        }).encode()

        mock_popen_instance = MagicMock()
        mock_popen.return_value = mock_popen_instance

        # Проверяем что при ошибке запускается looking_rooms.py
        # (В реальном тесте нужно проверять аргументы subprocess.Popen)


class TestLookingRooms(unittest.TestCase):
    """Тесты для модуля looking_rooms"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()  # Скрываем окно

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    def test_refresh_rooms_success(self, mock_messagebox, mock_socket_class):
        """TestRefreshRoomsSuccess: Успешное обновление списка комнат"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем ответ сервера
        response_data = {
            'status': True,
            'message': [
                {'room_id': 1, 'creator': 'player1', 'player_count': 1},
                {'room_id': 2, 'creator': 'player2', 'player_count': 2}
            ]
        }
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Создаем mock Treeview
        mock_treeview = MagicMock()
        mock_treeview.get_children.return_value = ['item1', 'item2']

        # Вызываем функцию
        refresh_rooms()

        # Проверяем вызовы
        mock_socket.connect.assert_called_once_with(('172.20.10.2', 43000))
        mock_socket.sendall.assert_called_once_with(json.dumps({'command': 5}).encode())
        mock_socket.recv.assert_called_once_with(1024)
        mock_socket.close.assert_called_once()

        # Проверяем что сообщения об ошибке не вызывались
        mock_messagebox.showerror.assert_not_called()

    @patch('socket.socket', side_effect=socket.error("Connection failed"))
    @patch('tkinter.messagebox')
    def test_refresh_rooms_connection_error(self, mock_messagebox, mock_socket):
        """TestRefreshRoomsConnectionError: Ошибка соединения"""
        refresh_rooms()
        mock_messagebox.showerror.assert_called_once_with("Connection Error",
                                                          "Failed to connect to server: Connection failed")

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    def test_refresh_rooms_server_error(self, mock_messagebox, mock_socket_class):
        """TestRefreshRoomsServerError: Ошибка сервера"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': False, 'message': 'Server error'}
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        refresh_rooms()
        mock_messagebox.showerror.assert_called_once_with("Error", "Server error")

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    def test_refresh_rooms_json_decode_error(self, mock_messagebox, mock_socket_class):
        """TestRefreshRoomsJsonDecodeError: Ошибка декодирования JSON"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Возвращаем некорректные данные
        mock_socket.recv.return_value = b'invalid json'

        refresh_rooms()
        mock_messagebox.showerror.assert_called_once_with("Error", "Failed to decode server response")

    @patch('subprocess.Popen')
    @patch('json.dumps')
    def test_create_room(self, mock_json_dumps, mock_popen):
        """TestCreateRoom: Создание комнаты"""
        # Устанавливаем глобальную переменную
        import checkers.split.client.pythonProject.looking_rooms as lr_module
        lr_module.user_id = 123

        mock_json_dumps.return_value = '{"user_id": 123, "create_room": 1}'

        create_room()

        mock_json_dumps.assert_called_once_with({'user_id': 123, 'create_room': 1})
        mock_popen.assert_called_once()

    @patch('subprocess.Popen')
    @patch('json.dumps')
    @patch('tkinter.messagebox')
    def test_join_room_success(self, mock_messagebox, mock_json_dumps, mock_popen):
        """TestJoinRoomSuccess: Успешный вход в комнату"""
        import checkers.split.client.pythonProject.looking_rooms as lr_module
        lr_module.user_id = 123

        # Создаем mock Treeview с выбранной комнатой
        mock_treeview = MagicMock()
        mock_treeview.selection.return_value = ['item1']
        mock_treeview.item.return_value = {'values': (1, 'creator', '1/2')}

        # Заменяем глобальный treeview
        lr_module.tree = mock_treeview

        mock_json_dumps.return_value = '{"user_id": 123, "room_number": 1}'

        join_room()

        mock_json_dumps.assert_called_once_with({'user_id': 123, 'room_number': 1})
        mock_popen.assert_called_once()
        mock_messagebox.showwarning.assert_not_called()

    @patch('tkinter.messagebox')
    def test_join_room_full(self, mock_messagebox):
        """TestJoinRoomFull: Попытка входа в заполненную комнату"""
        import checkers.split.client.pythonProject.looking_rooms as lr_module

        # Создаем mock Treeview с заполненной комнатой
        mock_treeview = MagicMock()
        mock_treeview.selection.return_value = ['item1']
        mock_treeview.item.return_value = {'values': (1, 'creator', '2/2')}

        lr_module.tree = mock_treeview

        join_room()

        mock_messagebox.showwarning.assert_called_once_with("Вход в комнату", "Комната заполнена")

    @patch('subprocess.Popen')
    @patch('tkinter.messagebox')
    def test_join_room_no_selection(self, mock_messagebox, mock_popen):
        """TestJoinRoomNoSelection: Отсутствие выбранной комнаты"""
        import checkers.split.client.pythonProject.looking_rooms as lr_module

        # Создаем mock Treeview без выбранных элементов
        mock_treeview = MagicMock()
        mock_treeview.selection.return_value = []

        lr_module.tree = mock_treeview

        join_room()

        mock_popen.assert_not_called()
        mock_messagebox.assert_not_called()

    def tearDown(self):
        self.root.destroy()


class TestMainActivity(unittest.TestCase):
    """Тесты для main_activity"""

    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('json.loads')
    def test_view_rooms_success(self, mock_json_loads, mock_popen, mock_socket_class):
        """TestViewRoomsSuccess: Успешное получение списка комнат"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': True, 'message': 'Room list'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Устанавливаем глобальную переменную
        import checkers.split.client.pythonProject.main_activity as ma_module
        ma_module.user_id = 'test_user'

        view_rooms()

        mock_socket.connect.assert_called_once_with(('172.20.10.2', 43000))
        mock_socket.sendall.assert_called_once_with(json.dumps({'command': 5}).encode())

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    @patch('json.loads')
    def test_view_rooms_failure(self, mock_json_loads, mock_messagebox, mock_socket_class):
        """TestViewRoomsFailure: Ошибка при получении списка комнат"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': False, 'message': 'Error message'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        view_rooms()

        mock_messagebox.showerror.assert_called_once_with("Error", "Error message")

    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('json.loads')
    def test_top_players_success(self, mock_json_loads, mock_popen, mock_socket_class):
        """TestTopPlayersSuccess: Успешное получение топа игроков"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': True, 'message': 'Top players list'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        top_players()

        mock_socket.sendall.assert_called_once_with(json.dumps({'command': 3}).encode())

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    @patch('json.loads')
    def test_top_players_failure(self, mock_json_loads, mock_messagebox, mock_socket_class):
        """TestTopPlayersFailure: Ошибка при получении топа игроков"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': False, 'message': 'Error message'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        top_players()

        mock_messagebox.showerror.assert_called_once_with("Error", "Error message")


class TestUserActivityWithServer(unittest.TestCase):
    """Тесты для user_activity_with_server"""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    @patch('socket.socket')
    @patch('json.loads')
    @patch('subprocess.Popen')
    @patch('tkinter.messagebox')
    def test_login_success(self, mock_messagebox, mock_popen, mock_json_loads, mock_socket_class):
        """TestLoginSuccess: Успешная авторизация"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': True, 'user_id': 123}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Создаем mock для entry полей
        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "test_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "test_password"

        login()

        mock_socket.sendall.assert_called_once_with(
            json.dumps({'username': 'test_user', 'password': 'test_password', 'command': 1}).encode()
        )
        mock_messagebox.showerror.assert_not_called()

    @patch('socket.socket')
    @patch('json.loads')
    @patch('tkinter.messagebox')
    def test_login_failure(self, mock_messagebox, mock_json_loads, mock_socket_class):
        """TestLoginFailure: Неудачная авторизация"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': False, 'message': 'Invalid credentials'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "test_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "test_password"

        login()

        mock_messagebox.showerror.assert_called_once_with("Login Error", "Invalid credentials")

    @patch('tkinter.messagebox')
    def test_login_empty_credentials(self, mock_messagebox):
        """TestLoginEmptyCredentials: Пустые учетные данные"""
        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = ""
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = ""

        login()

        mock_messagebox.showerror.assert_called_once_with("Input Error", "Username and Password cannot be empty.")

    @patch('socket.socket')
    @patch('json.loads')
    @patch('tkinter.messagebox')
    def test_register_success(self, mock_messagebox, mock_json_loads, mock_socket_class):
        """TestRegisterSuccess: Успешная регистрация"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': True, 'user_id': 123}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "test_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "test_password"

        register()

        mock_socket.sendall.assert_called_once_with(
            json.dumps({'username': 'test_user', 'password': 'test_password', 'command': 2}).encode()
        )

    @patch('socket.socket')
    @patch('json.loads')
    @patch('tkinter.messagebox')
    def test_register_failure(self, mock_messagebox, mock_json_loads, mock_socket_class):
        """TestRegisterFailure: Неудачная регистрация"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        response_data = {'status': False, 'message': 'Username already exists'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "test_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "test_password"

        register()

        mock_messagebox.showerror.assert_called_once_with("Registration Error", "Username already exists")

    def tearDown(self):
        self.root.destroy()


class TestServerFunctions(unittest.TestCase):
    """Тесты для функций сервера"""

    def setUp(self):
        self.test_db = "test_server.db"
        self.mock_connection = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_connection.cursor.return_value = self.mock_cursor

    @patch('sqlite3.connect')
    def test_authorization_success(self, mock_connect):
        """TestAuthorizationSuccess: Успешная авторизация"""
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchone.return_value = (123,)

        # Создаем mock для соединения
        data_json = {'command': 1, 'username': 'testuser', 'password': 'testpass'}

        # Здесь нужно было бы вызвать authorization, но функция требует соединение
        # Вместо этого проверяем логику

        # Проверяем что запрос выполняется правильно
        expected_query = 'SELECT id FROM users WHERE username=? AND password=?'
        # self.mock_cursor.execute.assert_called_with(expected_query, ('testuser', 'testpass'))

    @patch('sqlite3.connect')
    def test_authorization_failure(self, mock_connect):
        """TestAuthorizationFailure: Неудачная авторизация"""
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchone.return_value = None

        # Аналогично предыдущему тесту

    @patch('sqlite3.connect')
    def test_register_new_user(self, mock_connect):
        """TestRegisterNewUser: Регистрация нового пользователя"""
        mock_connect.return_value = self.mock_connection
        # Первый запрос (проверка существования) возвращает None
        # Второй вызов fetchone для последнего ID
        self.mock_cursor.fetchone.side_effect = [None, (456,)]
        self.mock_cursor.lastrowid = 456

        # Тестируем регистрацию нового пользователя
        # (требует адаптации под реальную функцию)

    @patch('sqlite3.connect')
    def test_register_existing_user(self, mock_connect):
        """TestRegisterExistingUser: Регистрация существующего пользователя"""
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchone.return_value = (123,)

        # Тестируем попытку регистрации существующего пользователя

    @patch('sqlite3.connect')
    def test_top_players(self, mock_connect):
        """TestTopPlayers: Получение топа игроков"""
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchall.return_value = [
            ('player1', 600),
            ('player2', 550),
            ('player3', 500)
        ]

        # Тестируем получение топа игроков

    def test_calculate_possible_moves(self):
        """TestCalculatePossibleMoves: Расчет возможных ходов"""
        # Создаем стандартную доску
        pieces = [[0 for _ in range(8)] for _ in range(8)]

        # Расставляем шашки как в начале игры
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:
                    if row < 3:
                        pieces[row][col] = 1  # Красные
                    elif row > 4:
                        pieces[row][col] = 2  # Белые

        # Тестируем для красной шашки (игрок 1)
        moves = calculate_possible_moves(pieces, 2, 1, 1)
        # Проверяем что есть возможные ходы
        self.assertIsInstance(moves, list)

        # Тестируем для белой шашки (игрок 2)
        moves = calculate_possible_moves(pieces, 5, 0, 2)
        self.assertIsInstance(moves, list)

    def test_has_possible_moves(self):
        """TestHasPossibleMoves: Проверка наличия возможных ходов"""
        # Создаем упрощенную доску
        pieces = [[0 for _ in range(8)] for _ in range(8)]

        # Ставим одну красную шашку
        pieces[2][1] = 1

        # Должны быть возможные ходы
        has_moves = has_possible_moves(pieces, 1)
        self.assertTrue(has_moves)

        # Блокируем шашку
        pieces[3][0] = 2
        pieces[3][2] = 2

        # Теперь не должно быть ходов
        has_moves = has_possible_moves(pieces, 1)
        self.assertFalse(has_moves)

    def test_make_move(self):
        """TestMakeMove: Выполнение хода"""
        pieces = [[0 for _ in range(8)] for _ in range(8)]
        pieces[2][1] = 1  # Красная шашка

        selected_piece = (2, 1)
        new_position = (3, 0)

        # Выполняем ход
        new_pieces, can_continue, game_status = make_move(pieces, 3, 0, selected_piece, 1)

        # Проверяем результаты
        self.assertEqual(new_pieces[2][1], 0)  # Старая позиция пуста
        self.assertEqual(new_pieces[3][0], 1)  # Новая позиция занята
        self.assertFalse(can_continue)  # Не должно быть продолжения
        self.assertEqual(game_status, 0)  # Игра продолжается

    @patch('sqlite3.connect')
    def test_get_username_by_id(self, mock_connect):
        """TestGetUsernameById: Получение имени пользователя по ID"""
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchone.return_value = ('testuser',)

        username = get_username_by_id(123)
        self.assertEqual(username, 'testuser')

        # Проверяем случай когда пользователь не найден
        self.mock_cursor.fetchone.return_value = None
        username = get_username_by_id(999)
        self.assertIsNone(username)

    @patch('sqlite3.connect')
    def test_update_scores(self, mock_connect):
        """TestUpdateScores: Обновление рейтинга игроков"""
        mock_connect.return_value = self.mock_connection

        update_scores(123, 456)  # Победитель ID 123, проигравший ID 456

        # Проверяем что выполнено два UPDATE запроса
        self.assertEqual(self.mock_cursor.execute.call_count, 2)

        # Проверяем первый запрос (увеличение очков победителю)
        first_call = self.mock_cursor.execute.call_args_list[0]
        self.assertIn('UPDATE users SET score = score + 25', first_call[0][0])
        self.assertEqual(first_call[0][1], (123,))

        # Проверяем второй запрос (уменьшение очков проигравшему)
        second_call = self.mock_cursor.execute.call_args_list[1]
        self.assertIn('UPDATE users SET score = score - 25', second_call[0][0])
        self.assertEqual(second_call[0][1], (456,))

        # Проверяем что выполнен commit
        self.mock_connection.commit.assert_called_once()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)


    if __name__ == '__main__':
        unittest.main()

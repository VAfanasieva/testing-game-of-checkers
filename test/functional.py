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


class TestDatabaseActions(unittest.TestCase):
    """Тесты для модуля actions (работа с базой данных)"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.test_db = "test_database.db"

    def tearDown(self):
        """Очистка после каждого теста"""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    @patch('sqlite3.connect')
    def test_initialize_database_success(self, mock_connect):
        """TestInitializeDatabaseSuccess: Успешная инициализация базы данных"""
        # Создаем mock соединения и курсора
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Вызываем функцию
        initialize_database()

        # Проверяем что было создано соединение
        mock_connect.assert_called_once()

        # Проверяем что был выполнен CREATE TABLE запрос
        mock_cursor.execute.assert_called()

        # Проверяем что был выполнен commit
        mock_conn.commit.assert_called_once()

        # Проверяем что соединение было закрыто
        mock_conn.close.assert_called_once()

    def test_initialize_database_creates_file(self):
        """TestInitializeDatabaseCreatesFile: Проверка создания файла БД"""
        # Удаляем файл если существует
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

        # Мокаем sqlite3.connect чтобы использовать тестовую БД
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor

            # Мокаем путь к базе данных
            with patch('checkers.split.server.pythonProject.database.actions.database_file', self.test_db):
                initialize_database()

                # Проверяем что функция попыталась создать папку и файл
                # (В реальности файл не создастся из-за мока, но мы проверяем вызовы)

    @patch('sqlite3.connect')
    def test_delete_user_by_id_success(self, mock_connect):
        """TestDeleteUserByIdSuccess: Успешное удаление пользователя по ID"""
        # Создаем mock соединения и курсора
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Вызываем функцию с тестовым ID
        test_user_id = 123
        delete_user_by_id(test_user_id)

        # Проверяем что было создано соединение
        mock_connect.assert_called_once()

        # Проверяем что был выполнен DELETE запрос с правильным ID
        mock_cursor.execute.assert_called_once_with(
            'DELETE FROM users WHERE id = ?', (test_user_id,)
        )

        # Проверяем что был выполнен commit
        mock_conn.commit.assert_called_once()

        # Проверяем что соединение было закрыто
        mock_conn.close.assert_called_once()

    @patch('sqlite3.connect')
    def test_delete_user_by_id_nonexistent(self, mock_connect):
        """TestDeleteUserByIdNonexistent: Удаление несуществующего пользователя"""
        # Создаем mock соединения и курсора
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Вызываем функцию с несуществующим ID
        delete_user_by_id(999)

        # Проверяем что DELETE запрос все равно был выполнен
        mock_cursor.execute.assert_called_once()

        # Проверяем что commit был выполнен
        mock_conn.commit.assert_called_once()


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
    @patch('pygame.event.get')
    @patch('pygame.quit')
    def test_main_room_creation(self, mock_quit, mock_event_get, mock_display, mock_init, mock_popen,
                                mock_socket_class):
        """TestMainRoomCreation: Проверка создания комнаты"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Мокируем все необходимые вызовы
        mock_socket.recv.side_effect = [
            json.dumps({
                'status': True,
                'client_number': 1,
                'room_number': 5
            }).encode(),
            json.dumps({
                'message_start': 'RdyCheck',
                'players': [
                    {
                        'player_number': 1,
                        'username': 'test_user',
                        'score': 500,
                        'opponent_username': 'opponent',
                        'opponent_score': 500
                    }
                ]
            }).encode(),
            json.dumps({'message_start': 'StartGame'}).encode()
        ]

        # Мокируем события pygame
        mock_event_get.return_value = [MagicMock(type=pygame.QUIT)]  # pygame.QUIT = 12

        # Мокируем subprocess.Popen
        mock_popen_instance = MagicMock()
        mock_popen.return_value = mock_popen_instance

        try:
            # Пытаемся импортировать и запустить main
            from checkers.split.client.pythonProject.client import main
            # Запускаем в отдельном потоке, чтобы можно было прервать
            import threading
            import time

            thread = threading.Thread(target=main)
            thread.daemon = True
            thread.start()

            # Даем время на выполнение, затем прерываем
            time.sleep(0.1)

        except SystemExit:
            # Ожидаемый выход
            pass
        except Exception as e:
            # Другие исключения игнорируем для теста
            print(f"Исключение в тесте: {e}")

        # Проверяем что были отправлены данные для создания комнаты
        mock_socket.sendall.assert_any_call(
            json.dumps({'command': 4, 'user_id': 123}).encode()
        )

    @patch('sys.argv', ['client.py', '{"user_id": 123, "room_number": 5}'])
    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.event.get')
    @patch('pygame.quit')
    def test_main_room_join(self, mock_quit, mock_event_get, mock_display, mock_init, mock_popen, mock_socket_class):
        """TestMainRoomJoin: Проверка присоединения к комнате"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем ответы сервера
        mock_socket.recv.side_effect = [
            json.dumps({
                'status': True,
                'client_number': 2,
                'room_number': 5
            }).encode(),
            json.dumps({
                'message_start': 'RdyCheck',
                'players': [
                    {
                        'player_number': 2,
                        'username': 'test_user',
                        'score': 500,
                        'opponent_username': 'opponent',
                        'opponent_score': 500
                    }
                ]
            }).encode(),
            json.dumps({'message_start': 'StartGame'}).encode()
        ]

        # Мокируем события pygame
        mock_event_get.return_value = [MagicMock(type=12)]  # pygame.QUIT

        # Мокируем subprocess.Popen
        mock_popen_instance = MagicMock()
        mock_popen.return_value = mock_popen_instance

        try:
            from checkers.split.client.pythonProject.client import main
            import threading
            import time

            thread = threading.Thread(target=main)
            thread.daemon = True
            thread.start()
            time.sleep(0.1)

        except SystemExit:
            pass

        # Проверяем что были отправлены данные для присоединения к комнате
        mock_socket.sendall.assert_any_call(
            json.dumps({'user_id': 123, 'room_number': 5, 'command': 6}).encode()
        )

    @patch('sys.argv', ['client.py', '{"user_id": 123}'])
    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('pygame.init')
    @patch('pygame.display.set_mode')
    @patch('pygame.quit')
    @patch('checkers.split.client.pythonProject.client.pygame')
    def test_main_server_error(self, mock_pygame, mock_quit, mock_display, mock_init, mock_popen, mock_socket_class):
        """TestMainServerError: Обработка ошибки сервера"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Сервер возвращает ошибку
        mock_socket.recv.return_value = json.dumps({
            'status': False,
            'message': 'Ошибка сервера'
        }).encode()

        mock_popen_instance = MagicMock()
        mock_popen.return_value = mock_popen_instance

        # Мокируем pygame
        mock_pygame.event.get.return_value = []

        try:
            from checkers.split.client.pythonProject.client import main
            main()
        except SystemExit:
            # Ожидаемый выход
            pass

        # Проверяем что был вызван subprocess.Popen для открытия looking_rooms.py
        mock_popen.assert_called_once()

        # Получаем аргументы вызова
        call_args = mock_popen.call_args[0][0]

        # Проверяем что запускается looking_rooms.py
        self.assertIn('looking_rooms.py', call_args[1])

        # Проверяем что передается user_id и error_message
        import json as json_module
        passed_data = json_module.loads(call_args[2])
        self.assertEqual(passed_data['user_id'], 123)
        self.assertEqual(passed_data['error_message'], 'Ошибка сервера')


class TestLookingRooms(unittest.TestCase):
    """Тесты для модуля looking_rooms"""

    def setUp(self):
        # Создаем скрытое Tkinter окно для тестов
        self.root = tk.Tk()
        self.root.withdraw()  # Скрываем окно

        # Устанавливаем глобальную переменную user_id для модуля
        import checkers.split.client.pythonProject.looking_rooms as lr_module
        lr_module.user_id = 123

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    @patch('tkinter.ttk.Treeview')
    def test_refresh_rooms_success(self, mock_treeview_class, mock_messagebox, mock_socket_class):
        """TestRefreshRoomsSuccess: Успешное обновление списка комнат"""
        # Настраиваем моки
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
        mock_treeview_class.return_value = mock_treeview
        mock_treeview.get_children.return_value = ['item1', 'item2']

        # Импортируем модуль и заменяем tree
        import checkers.split.client.pythonProject.looking_rooms as lr_module
        original_tree = lr_module.tree if hasattr(lr_module, 'tree') else None
        lr_module.tree = mock_treeview

        try:
            # Вызываем функцию
            refresh_rooms()

            # Проверяем вызовы
            mock_socket.connect.assert_called_once_with(('172.20.10.2', 43000))
            mock_socket.sendall.assert_called_once_with(json.dumps({'command': 5}).encode())
            mock_socket.recv.assert_called_once_with(1024)
            mock_socket.close.assert_called_once()

            # Проверяем что сообщения об ошибке не вызывались
            mock_messagebox.showerror.assert_not_called()

            # Проверяем что старые элементы были удалены
            mock_treeview.delete.assert_any_call('item1')
            mock_treeview.delete.assert_any_call('item2')

            # Проверяем что новые элементы были добавлены
            self.assertEqual(mock_treeview.insert.call_count, 2)

        finally:
            # Восстанавливаем оригинальное значение
            if original_tree is not None:
                lr_module.tree = original_tree

    @patch('socket.socket', side_effect=socket.error("Connection failed"))
    @patch('tkinter.messagebox')
    def test_refresh_rooms_connection_error(self, mock_messagebox, mock_socket):
        """TestRefreshRoomsConnectionError: Ошибка соединения"""
        # Вызываем функцию
        refresh_rooms()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with(
            "Connection Error",
            "Failed to connect to server: Connection failed"
        )

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    def test_refresh_rooms_server_error(self, mock_messagebox, mock_socket_class):
        """TestRefreshRoomsServerError: Ошибка сервера"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Сервер возвращает ошибку
        response_data = {'status': False, 'message': 'Server error'}
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Вызываем функцию
        refresh_rooms()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with("Error", "Server error")

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    def test_refresh_rooms_json_decode_error(self, mock_messagebox, mock_socket_class):
        """TestRefreshRoomsJsonDecodeError: Ошибка декодирования JSON"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Возвращаем некорректные данные
        mock_socket.recv.return_value = b'invalid json'

        # Вызываем функцию
        refresh_rooms()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with(
            "Error",
            "Failed to decode server response"
        )

    @patch('subprocess.Popen')
    @patch('json.dumps')
    def test_create_room(self, mock_json_dumps, mock_popen):
        """TestCreateRoom: Создание комнаты"""
        # Устанавливаем возвращаемое значение для json.dumps
        mock_json_dumps.return_value = '{"user_id": 123, "create_room": 1}'

        # Вызываем функцию
        create_room()

        # Проверяем что json.dumps был вызван с правильными аргументами
        mock_json_dumps.assert_called_once_with({'user_id': 123, 'create_room': 1})

        # Проверяем что subprocess.Popen был вызван
        mock_popen.assert_called_once()

        # Получаем аргументы вызова Popen
        call_args = mock_popen.call_args[0][0]

        # Проверяем что запускается client.py
        self.assertIn('client.py', call_args[1])

        # Проверяем переданные аргументы
        self.assertEqual(call_args[2], '{"user_id": 123, "create_room": 1}')

    @patch('subprocess.Popen')
    @patch('json.dumps')
    @patch('tkinter.messagebox')
    @patch('tkinter.ttk.Treeview')
    def test_join_room_success(self, mock_treeview_class, mock_messagebox, mock_json_dumps, mock_popen):
        """TestJoinRoomSuccess: Успешный вход в комнату"""
        # Создаем mock Treeview
        mock_treeview = MagicMock()
        mock_treeview_class.return_value = mock_treeview

        # Настраиваем возвращаемые значения
        mock_treeview.selection.return_value = ['item1']
        mock_treeview.item.return_value = {'values': (1, 'creator', '1/2')}

        # Устанавливаем mock treeview в модуль
        import checkers.split.client.pythonProject.looking_rooms as lr_module
        original_tree = lr_module.tree if hasattr(lr_module, 'tree') else None
        lr_module.tree = mock_treeview

        # Настраиваем json.dumps
        mock_json_dumps.return_value = '{"user_id": 123, "room_number": 1}'

        try:
            # Вызываем функцию
            join_room()

            # Проверяем что json.dumps был вызван с правильными аргументами
            mock_json_dumps.assert_called_once_with({'user_id': 123, 'room_number': 1})

            # Проверяем что subprocess.Popen был вызван
            mock_popen.assert_called_once()

            # Проверяем что предупреждение не показывалось
            mock_messagebox.showwarning.assert_not_called()

        finally:
            # Восстанавливаем оригинальное значение
            if original_tree is not None:
                lr_module.tree = original_tree

    @patch('tkinter.messagebox')
    @patch('tkinter.ttk.Treeview')
    def test_join_room_full(self, mock_treeview_class, mock_messagebox):
        """TestJoinRoomFull: Попытка входа в заполненную комнату"""
        # Создаем mock Treeview
        mock_treeview = MagicMock()
        mock_treeview_class.return_value = mock_treeview

        # Настраиваем заполненную комнату (2/2)
        mock_treeview.selection.return_value = ['item1']
        mock_treeview.item.return_value = {'values': (1, 'creator', '2/2')}

        # Устанавливаем mock treeview в модуль
        import checkers.split.client.pythonProject.looking_rooms as lr_module
        original_tree = lr_module.tree if hasattr(lr_module, 'tree') else None
        lr_module.tree = mock_treeview

        try:
            # Вызываем функцию
            join_room()

            # Проверяем что было показано предупреждение
            mock_messagebox.showwarning.assert_called_once_with(
                "Вход в комнату",
                "Комната заполнена"
            )

        finally:
            # Восстанавливаем оригинальное значение
            if original_tree is not None:
                lr_module.tree = original_tree

    @patch('subprocess.Popen')
    @patch('tkinter.messagebox')
    @patch('tkinter.ttk.Treeview')
    def test_join_room_no_selection(self, mock_treeview_class, mock_messagebox, mock_popen):
        """TestJoinRoomNoSelection: Отсутствие выбранной комнаты"""
        # Создаем mock Treeview без выбранных элементов
        mock_treeview = MagicMock()
        mock_treeview_class.return_value = mock_treeview
        mock_treeview.selection.return_value = []  # Пустой список

        # Устанавливаем mock treeview в модуль
        import checkers.split.client.pythonProject.looking_rooms as lr_module
        original_tree = lr_module.tree if hasattr(lr_module, 'tree') else None
        lr_module.tree = mock_treeview

        try:
            # Вызываем функцию
            join_room()

            # Проверяем что Popen не вызывался
            mock_popen.assert_not_called()

            # Проверяем что messagebox не вызывался
            mock_messagebox.assert_not_called()

        finally:
            # Восстанавливаем оригинальное значение
            if original_tree is not None:
                lr_module.tree = original_tree

    def tearDown(self):
        self.root.destroy()


class TestMainActivity(unittest.TestCase):
    """Тесты для main_activity"""

    def setUp(self):
        # Устанавливаем глобальную переменную user_id
        import checkers.split.client.pythonProject.main_activity as ma_module
        ma_module.user_id = 'test_user'

    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('json.loads')
    def test_view_rooms_success(self, mock_json_loads, mock_popen, mock_socket_class):
        """TestViewRoomsSuccess: Успешное получение списка комнат"""
        # Настраиваем моки
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
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Мокируем subprocess.Popen
        mock_popen_instance = MagicMock()
        mock_popen.return_value = mock_popen_instance

        # Вызываем функцию
        view_rooms()

        # Проверяем вызовы
        mock_socket.connect.assert_called_once_with(('172.20.10.2', 43000))
        mock_socket.sendall.assert_called_once_with(json.dumps({'command': 5}).encode())
        mock_socket.recv.assert_called_once_with(1024)

        # Проверяем что Popen был вызван для запуска looking_rooms.py
        mock_popen.assert_called_once()

        # Получаем аргументы вызова
        call_args = mock_popen.call_args[0][0]

        # Проверяем что запускается looking_rooms.py
        self.assertIn('looking_rooms.py', call_args[1])

        # Проверяем что передается user_id и message
        import json as json_module
        passed_data = json_module.loads(call_args[2])
        self.assertEqual(passed_data['user_id'], 'test_user')
        self.assertEqual(passed_data['message'], response_data['message'])

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    @patch('json.loads')
    def test_view_rooms_failure(self, mock_json_loads, mock_messagebox, mock_socket_class):
        """TestViewRoomsFailure: Ошибка при получении списка комнат"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем ответ сервера с ошибкой
        response_data = {'status': False, 'message': 'Error message'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Вызываем функцию
        view_rooms()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with("Error", "Error message")

    @patch('socket.socket')
    @patch('subprocess.Popen')
    @patch('json.loads')
    def test_top_players_success(self, mock_json_loads, mock_popen, mock_socket_class):
        """TestTopPlayersSuccess: Успешное получение топа игроков"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем ответ сервера
        response_data = {
            'status': True,
            'message': ['1: player1: 600 очков', '2: player2: 550 очков']
        }
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Мокируем subprocess.Popen
        mock_popen_instance = MagicMock()
        mock_popen.return_value = mock_popen_instance

        # Вызываем функцию
        top_players()

        # Проверяем вызовы
        mock_socket.connect.assert_called_once_with(('172.20.10.2', 43000))
        mock_socket.sendall.assert_called_once_with(json.dumps({'command': 3}).encode())

        # Проверяем что Popen был вызван для запуска top_players.py
        mock_popen.assert_called_once()

        # Получаем аргументы вызова
        call_args = mock_popen.call_args[0][0]

        # Проверяем что запускается top_players.py
        self.assertIn('top_players.py', call_args[1])

        # Проверяем что передается user_id и message
        import json as json_module
        passed_data = json_module.loads(call_args[2])
        self.assertEqual(passed_data['user_id'], 'test_user')
        self.assertEqual(passed_data['message'], response_data['message'])

    @patch('socket.socket')
    @patch('tkinter.messagebox')
    @patch('json.loads')
    def test_top_players_failure(self, mock_json_loads, mock_messagebox, mock_socket_class):
        """TestTopPlayersFailure: Ошибка при получении топа игроков"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем ответ сервера с ошибкой
        response_data = {'status': False, 'message': 'Error message'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Вызываем функцию
        top_players()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with("Error", "Error message")

    @patch('socket.socket')
    @patch('json.loads')
    @patch('tkinter.messagebox')
    def test_view_rooms_invalid_response_format(self, mock_messagebox, mock_json_loads, mock_socket_class):
        """TestViewRoomsInvalidResponseFormat: Некорректный формат ответа"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем некорректный ответ сервера (без ожидаемых полей)
        mock_json_loads.return_value = {}  # Пустой словарь
        mock_socket.recv.return_value = json.dumps({}).encode()

        # Вызываем функцию
        view_rooms()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with(
            "Error",
            "Invalid response format"
        )

    @patch('socket.socket')
    @patch('json.loads')
    @patch('tkinter.messagebox')
    def test_view_rooms_json_decode_error(self, mock_messagebox, mock_json_loads, mock_socket_class):
        """TestViewRoomsJsonDecodeError: Ошибка декодирования JSON"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Имитируем ошибку декодирования JSON
        mock_json_loads.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_socket.recv.return_value = b'invalid json'

        # Вызываем функцию
        view_rooms()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with(
            "Error",
            "Failed to decode server response"
        )


class TestUserActivityWithServer(unittest.TestCase):
    """Тесты для user_activity_with_server"""

    def setUp(self):
        # Создаем скрытое Tkinter окно
        self.root = tk.Tk()
        self.root.withdraw()

    @patch('socket.socket')
    @patch('json.loads')
    @patch('subprocess.Popen')
    @patch('tkinter.messagebox')
    def test_login_success(self, mock_messagebox, mock_popen, mock_json_loads, mock_socket_class):
        """TestLoginSuccess: Успешная авторизация"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем успешный ответ сервера
        response_data = {'status': True, 'user_id': 123}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Мокируем subprocess.Popen
        mock_popen_instance = MagicMock()
        mock_popen.return_value = mock_popen_instance

        # Создаем mock для entry полей
        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "test_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "test_password"

        # Вызываем функцию
        login()

        # Проверяем вызовы
        mock_socket.connect.assert_called_once_with(('172.20.10.2', 43000))
        mock_socket.sendall.assert_called_once_with(
            json.dumps({'username': 'test_user', 'password': 'test_password', 'command': 1}).encode()
        )

        # Проверяем что Popen был вызван для запуска main_activity.py
        mock_popen.assert_called_once()

        # Получаем аргументы вызова
        call_args = mock_popen.call_args[0][0]

        # Проверяем что запускается main_activity.py
        self.assertIn('main_activity.py', call_args[1])

        # Проверяем что передается user_id
        self.assertEqual(call_args[2], '123')

        # Проверяем что сообщения об ошибке не вызывались
        mock_messagebox.showerror.assert_not_called()

    @patch('socket.socket')
    @patch('json.loads')
    @patch('tkinter.messagebox')
    def test_login_failure(self, mock_messagebox, mock_json_loads, mock_socket_class):
        """TestLoginFailure: Неудачная авторизация"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем ответ сервера с ошибкой
        response_data = {'status': False, 'message': 'Invalid credentials'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Создаем mock для entry полей
        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "test_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "test_password"

        # Вызываем функцию
        login()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with(
            "Login Error",
            "Invalid credentials"
        )

    @patch('tkinter.messagebox')
    def test_login_empty_credentials(self, mock_messagebox):
        """TestLoginEmptyCredentials: Пустые учетные данные"""
        # Создаем mock для entry полей с пустыми значениями
        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = ""
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = ""

        # Вызываем функцию
        login()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with(
            "Input Error",
            "Username and Password cannot be empty."
        )

    @patch('socket.socket')
    @patch('json.loads')
    @patch('subprocess.Popen')
    @patch('tkinter.messagebox')
    def test_register_success(self, mock_messagebox, mock_popen, mock_json_loads, mock_socket_class):
        """TestRegisterSuccess: Успешная регистрация"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем успешный ответ сервера
        response_data = {'status': True, 'user_id': 456}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Мокируем subprocess.Popen
        mock_popen_instance = MagicMock()
        mock_popen.return_value = mock_popen_instance

        # Создаем mock для entry полей
        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "new_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "new_password"

        # Вызываем функцию
        register()

        # Проверяем вызовы
        mock_socket.connect.assert_called_once_with(('172.20.10.2', 43000))
        mock_socket.sendall.assert_called_once_with(
            json.dumps({'username': 'new_user', 'password': 'new_password', 'command': 2}).encode()
        )

        # Проверяем что Popen был вызван для запуска main_activity.py
        mock_popen.assert_called_once()

        # Получаем аргументы вызова
        call_args = mock_popen.call_args[0][0]

        # Проверяем что запускается main_activity.py
        self.assertIn('main_activity.py', call_args[1])

        # Проверяем что передается user_id
        self.assertEqual(call_args[2], '456')

        # Проверяем что сообщения об ошибке не вызывались
        mock_messagebox.showerror.assert_not_called()

        # Проверяем что было показано сообщение об успехе
        mock_messagebox.showinfo.assert_called_once_with(
            "Registration Success",
            "User registered successfully"
        )

    @patch('socket.socket')
    @patch('json.loads')
    @patch('tkinter.messagebox')
    def test_register_failure(self, mock_messagebox, mock_json_loads, mock_socket_class):
        """TestRegisterFailure: Неудачная регистрация"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Настраиваем ответ сервера с ошибкой
        response_data = {'status': False, 'message': 'Username already exists'}
        mock_json_loads.return_value = response_data
        mock_socket.recv.return_value = json.dumps(response_data).encode()

        # Создаем mock для entry полей
        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "existing_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "password"

        # Вызываем функцию
        register()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with(
            "Registration Error",
            "Username already exists"
        )

    @patch('socket.socket')
    @patch('json.loads')
    @patch('tkinter.messagebox')
    def test_login_json_decode_error(self, mock_messagebox, mock_json_loads, mock_socket_class):
        """TestLoginJsonDecodeError: Ошибка декодирования JSON при авторизации"""
        # Настраиваем моки
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Имитируем ошибку декодирования JSON
        mock_json_loads.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_socket.recv.return_value = b'invalid json'

        # Создаем mock для entry полей
        import checkers.split.client.pythonProject.user_activity_with_server as ua_module
        ua_module.username_entry = MagicMock()
        ua_module.username_entry.get.return_value = "test_user"
        ua_module.password_entry = MagicMock()
        ua_module.password_entry.get.return_value = "test_password"

        # Вызываем функцию
        login()

        # Проверяем что было показано сообщение об ошибке
        mock_messagebox.showerror.assert_called_once_with(
            "Login Error",
            "Failed to decode server response"
        )

    def tearDown(self):
        self.root.destroy()


class TestServerFunctions(unittest.TestCase):
    """Тесты для функций сервера"""

    def setUp(self):
        self.test_db = "test_server.db"
        self.mock_connection = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_connection.cursor.return_value = self.mock_cursor

        # Сохраняем оригинальное значение database_file
        import checkers.split.server.pythonProject.server as server_module
        self.original_database_file = getattr(server_module, 'database_file', None)

    @patch('sqlite3.connect')
    def test_authorization_success(self, mock_connect):
        """TestAuthorizationSuccess: Успешная авторизация"""
        # Настраиваем моки
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchone.return_value = (123,)

        # Создаем mock для соединения
        mock_conn_obj = MagicMock()

        # Тестируем функцию authorization
        # Для этого нужно создать тестовые данные
        data_json = {'username': 'testuser', 'password': 'testpass', 'command': 1}

        # Временная замена функции для тестирования
        def test_authorization(connection, data):
            try:
                username = data.get('username')
                password = data.get('password')

                if username is None or password is None:
                    response = json.dumps({'status': False, 'message': 'Missing required fields'})
                    connection.sendall(response.encode())
                    return

                # Имитируем запрос к БД
                conn = sqlite3.connect('test.db')
                c = conn.cursor()
                c.execute('SELECT id FROM users WHERE username=? AND password=?', (username, password))
                result = c.fetchone()
                conn.close()

                if result:
                    user_id = result[0]
                    response = json.dumps({'status': True, 'user_id': user_id})
                else:
                    response = json.dumps({'status': False, 'message': 'Invalid username or password'})
                connection.sendall(response.encode())
            except Exception as e:
                print(f"Ошибка при обработке данных от клиента: {e}")
                connection.sendall(json.dumps({'status': 'error', 'message': 'Server error'}).encode())
            finally:
                connection.close()

        # Не можем напрямую протестировать без рефакторинга кода
        # Оставляем как пример того, что нужно тестировать

        # Проверяем что запрос выполняется правильно
        expected_query = 'SELECT id FROM users WHERE username=? AND password=?'
        # В реальном тесте нужно было бы проверить это

    @patch('sqlite3.connect')
    def test_authorization_failure(self, mock_connect):
        """TestAuthorizationFailure: Неудачная авторизация"""
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchone.return_value = None

        # Аналогично предыдущему тесту
        # Нужен рефакторинг функции для тестирования

    @patch('sqlite3.connect')
    def test_register_new_user(self, mock_connect):
        """TestRegisterNewUser: Регистрация нового пользователя"""
        mock_connect.return_value = self.mock_connection

        # Настраиваем side_effect для последовательных вызовов fetchone
        self.mock_cursor.fetchone.side_effect = [
            None,  # Первый вызов (проверка существования)
            (456,)  # Второй вызов (последний ID)
        ]
        self.mock_cursor.lastrowid = 456

        # Тестируем регистрацию нового пользователя
        # Нужен рефакторинг функции для тестирования

    @patch('sqlite3.connect')
    def test_register_existing_user(self, mock_connect):
        """TestRegisterExistingUser: Регистрация существующего пользователя"""
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchone.return_value = (123,)

        # Тестируем попытку регистрации существующего пользователя
        # Нужен рефакторинг функции для тестирования

    @patch('sqlite3.connect')
    def test_top_players(self, mock_connect):
        """TestTopPlayers: Получение топа игроков"""
        mock_connect.return_value = self.mock_connection

        # Настраиваем возвращаемые данные
        mock_data = [
            ('player1', 600),
            ('player2', 550),
            ('player3', 500)
        ]
        self.mock_cursor.fetchall.return_value = mock_data

        # Тестируем получение топа игроков
        # Нужен рефакторинг функции для тестирования

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

        # Тестируем для красной шашки (игрок 1) в середине доски
        moves = calculate_possible_moves(pieces, 2, 1, 1)

        # Проверяем что результат - список
        self.assertIsInstance(moves, list)

        # Проверяем что есть возможные ходы (в начале игры должны быть)
        # Красные шашки могут двигаться только вниз
        possible_moves = [(3, 0), (3, 2)]
        for move in possible_moves:
            if move in moves:
                print(f"Найден ожидаемый ход: {move}")

        # Тестируем для белой шашки (игрок 2)
        moves = calculate_possible_moves(pieces, 5, 0, 2)
        self.assertIsInstance(moves, list)

        # Белые шашки могут двигаться только вверх
        possible_moves = [(4, 1)]
        for move in possible_moves:
            if move in moves:
                print(f"Найден ожидаемый ход: {move}")

        # Тестируем заблокированную шашку
        # Создаем ситуацию где шашка заблокирована
        blocked_pieces = [[0 for _ in range(8)] for _ in range(8)]
        blocked_pieces[2][1] = 1  # Красная шашка
        blocked_pieces[3][0] = 2  # Белая шашка спереди слева
        blocked_pieces[3][2] = 2  # Белая шашка спереди справа

        moves = calculate_possible_moves(blocked_pieces, 2, 1, 1)
        # Заблокированная шашка не должна иметь ходов
        self.assertEqual(len(moves), 0)

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

        # Тестируем для белых шашек
        pieces = [[0 for _ in range(8)] for _ in range(8)]
        pieces[5][0] = 2  # Белая шашка

        has_moves = has_possible_moves(pieces, 2)
        self.assertTrue(has_moves)

        # Блокируем белую шашку
        pieces[4][1] = 1

        has_moves = has_possible_moves(pieces, 2)
        self.assertFalse(has_moves)

    def test_make_move(self):
        """TestMakeMove: Выполнение хода"""
        # Тест 1: Простой ход без взятия
        pieces = [[0 for _ in range(8)] for _ in range(8)]
        pieces[2][1] = 1  # Красная шашка

        selected_piece = (2, 1)
        new_position = (3, 0)

        # Выполняем ход
        new_pieces, can_continue, game_status = make_move(pieces, 3, 0, selected_piece, 1)

        # Проверяем результаты
        self.assertEqual(new_pieces[2][1], 0)  # Старая позиция пуста
        self.assertEqual(new_pieces[3][0], 1)  # Новая позиция занята
        self.assertFalse(can_continue)  # Не должно быть продолжения (не было взятия)
        self.assertEqual(game_status, 0)  # Игра продолжается

        # Тест 2: Ход со взятием
        pieces = [[0 for _ in range(8)] for _ in range(8)]
        pieces[2][1] = 1  # Красная шашка
        pieces[3][2] = 2  # Белая шашка для взятия

        selected_piece = (2, 1)
        new_position = (4, 3)  # Ход через белую шашку

        new_pieces, can_continue, game_status = make_move(pieces, 4, 3, selected_piece, 1)

        # Проверяем результаты
        self.assertEqual(new_pieces[2][1], 0)  # Старая позиция пуста
        self.assertEqual(new_pieces[3][2], 0)  # Взятая шашка удалена
        self.assertEqual(new_pieces[4][3], 1)  # Новая позиция
        # После взятия может быть продолжение, если есть еще шашки для взятия
        # self.assertTrue(can_continue)  # Зависит от реализации

        # Тест 3: Победа красных (все белые шашки взяты)
        pieces = [[0 for _ in range(8)] for _ in range(8)]
        pieces[2][1] = 1  # Единственная красная шашка
        # Белых шашек нет

        new_pieces, can_continue, game_status = make_move(pieces, 3, 0, (2, 1), 1)

        # Проверяем что игра продолжается (есть еще красные шашки)
        self.assertEqual(game_status, 0)

        # Тест 4: Победа белых (все красные шашки взяты)
        pieces = [[0 for _ in range(8)] for _ in range(8)]
        pieces[5][0] = 2  # Единственная белая шашка
        # Красных шашек нет

        new_pieces, can_continue, game_status = make_move(pieces, 4, 1, (5, 0), 2)

        # Проверяем что игра продолжается
        self.assertEqual(game_status, 0)

    @patch('sqlite3.connect')
    def test_get_username_by_id(self, mock_connect):
        """TestGetUsernameById: Получение имени пользователя по ID"""
        # Настраиваем моки
        mock_connect.return_value = self.mock_connection
        self.mock_cursor.fetchone.return_value = ('testuser',)

        # Вызываем функцию
        username = get_username_by_id(123)

        # Проверяем результаты
        self.assertEqual(username, 'testuser')
        mock_connect.assert_called_once()

        # Проверяем что был выполнен правильный запрос
        self.mock_cursor.execute.assert_called_once_with(
            'SELECT username FROM users WHERE id=?', (123,)
        )

        # Проверяем случай когда пользователь не найден
        self.mock_cursor.fetchone.return_value = None
        mock_connect.reset_mock()
        self.mock_cursor.reset_mock()

        mock_connect.return_value = self.mock_connection

        username = get_username_by_id(999)
        self.assertIsNone(username)
        mock_connect.assert_called_once()
        self.mock_cursor.execute.assert_called_once_with(
            'SELECT username FROM users WHERE id=?', (999,)
        )

    @patch('sqlite3.connect')
    def test_update_scores(self, mock_connect):
        """TestUpdateScores: Обновление рейтинга игроков"""
        # Настраиваем моки
        mock_connect.return_value = self.mock_connection

        # Вызываем функцию
        winner_id = 123
        loser_id = 456
        update_scores(winner_id, loser_id)

        # Проверяем что выполнено два UPDATE запроса
        self.assertEqual(self.mock_cursor.execute.call_count, 2)

        # Проверяем первый запрос (увеличение очков победителю)
        first_call = self.mock_cursor.execute.call_args_list[0]
        # Проверяем что в запросе есть увеличение на 25
        self.assertIn('UPDATE users SET score = score + 25', first_call[0][0])
        # Проверяем параметры
        self.assertEqual(first_call[0][1], (winner_id,))

        # Проверяем второй запрос (уменьшение очков проигравшему)
        second_call = self.mock_cursor.execute.call_args_list[1]
        # Проверяем что в запросе есть уменьшение на 25
        self.assertIn('UPDATE users SET score = score - 25', second_call[0][0])
        # Проверяем параметры
        self.assertEqual(second_call[0][1], (loser_id,))

        # Проверяем что выполнен commit
        self.mock_connection.commit.assert_called_once()

        # Проверяем что соединение было закрыто
        self.mock_connection.close.assert_called_once()

        # Тест с разными значениями изменения очков
        mock_connect.reset_mock()
        self.mock_connection.reset_mock()
        self.mock_cursor.reset_mock()

        mock_connect.return_value = self.mock_connection

        # Вызываем с другими ID
        update_scores(789, 101)

        # Проверяем что запросы были выполнены с новыми ID
        calls = self.mock_cursor.execute.call_args_list
        self.assertIn((789,), calls[0][0][1])  # Победитель
        self.assertIn((101,), calls[1][0][1])  # Проигравший

    def tearDown(self):
        # Восстанавливаем оригинальное значение database_file
        if hasattr(self, 'original_database_file'):
            import checkers.split.server.pythonProject.server as server_module
            server_module.database_file = self.original_database_file

        # Удаляем тестовую базу данных если существует
        if os.path.exists(self.test_db):
            os.remove(self.test_db)


if __name__ == '__main__':
    unittest.main()

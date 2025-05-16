/**
 * Точка входа в клиентское приложение
 * @module index
 */

import { render } from 'solid-js/web'
import App from './App'

import './styles.css'

// Рендеринг приложения в корневой элемент
render(() => <App />, document.getElementById('root') as HTMLElement)

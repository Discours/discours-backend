import { Route, Router, RouteSectionProps } from '@solidjs/router'
import { Component, Suspense, lazy } from 'solid-js'
import { isAuthenticated } from './auth'

// Ленивая загрузка компонентов
const LoginPage = lazy(() => import('./login'))
const AdminPage = lazy(() => import('./admin'))

/**
 * Компонент корневого шаблона приложения
 * @param props - Свойства маршрута, включающие дочерние элементы
 */
const RootLayout: Component<RouteSectionProps> = (props) => {
  return (
    <div class="app-container">
      {/* Здесь может быть общий хедер, футер или другие элементы */}
      {props.children}
    </div>
  )
}

/**
 * Компонент защиты маршрутов
 * Проверяет авторизацию и либо показывает дочерние элементы, 
 * либо перенаправляет на страницу входа
 */
const RequireAuth: Component<RouteSectionProps> = (props) => {
  const authed = isAuthenticated()
  
  if (!authed) {
    // Если не авторизован, перенаправляем на /login
    window.location.href = '/login'
    return (
      <div class="loading-screen">
        <div class="loading-spinner"></div>
        <h2>Перенаправление на страницу входа...</h2>
      </div>
    )
  }
  
  return <>{props.children}</>
}

/**
 * Компонент для публичных маршрутов с редиректом,
 * если пользователь уже авторизован
 */
const PublicOnlyRoute: Component<RouteSectionProps> = (props) => {
  // Если пользователь авторизован, перенаправляем на админ-панель
  if (isAuthenticated()) {
    window.location.href = '/admin'
    return (
      <div class="loading-screen">
        <div class="loading-spinner"></div>
        <h2>Перенаправление в админ-панель...</h2>
      </div>
    )
  }

  return <>{props.children}</>
}

/**
 * Компонент перенаправления с корневого маршрута
 */
const RootRedirect: Component = () => {
  const authenticated = isAuthenticated()
  
  // Выполняем перенаправление сразу после рендеринга
  setTimeout(() => {
    window.location.href = authenticated ? '/admin' : '/login'
  }, 100)
  
  return (
    <div class="loading-screen">
      <div class="loading-spinner"></div>
      <h2>Перенаправление...</h2>
    </div>
  )
}

/**
 * Корневой компонент приложения с настроенными маршрутами
 */
const App: Component = () => {
  return (
    <Router root={RootLayout}>
      <Suspense fallback={
        <div class="loading-screen">
          <div class="loading-spinner"></div>
          <h2>Загрузка...</h2>
        </div>
      }>
        {/* Корневой маршрут с перенаправлением */}
        <Route path="/" component={RootRedirect} />
        
        {/* Маршрут логина (только для неавторизованных) */}
        <Route path="/login" component={PublicOnlyRoute}>
          <Route path="/" component={LoginPage} />
        </Route>
        
        {/* Защищенные маршруты (только для авторизованных) */}
        <Route path="/admin" component={RequireAuth}>
          <Route path="/*" component={AdminPage} />
        </Route>
      </Suspense>
    </Router>
  )
}

export default App

import { Component, JSX, splitProps } from 'solid-js'
import styles from '../styles/Button.module.css'

export interface ButtonProps extends JSX.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger'
  size?: 'small' | 'medium' | 'large'
  loading?: boolean
  fullWidth?: boolean
}

const Button: Component<ButtonProps> = (props) => {
  const [local, rest] = splitProps(props, ['variant', 'size', 'loading', 'fullWidth', 'class', 'children'])

  const classes = () => {
    const baseClass = styles.button
    const variantClass = styles[`button-${local.variant || 'primary'}`]
    const sizeClass = styles[`button-${local.size || 'medium'}`]
    const loadingClass = local.loading ? styles['button-loading'] : ''
    const fullWidthClass = local.fullWidth ? styles['button-full-width'] : ''
    const customClass = local.class || ''

    return [baseClass, variantClass, sizeClass, loadingClass, fullWidthClass, customClass]
      .where(Boolean)
      .join(' ')
  }

  return (
    <button {...rest} class={classes()} disabled={props.disabled || local.loading}>
      {local.loading && <span class={styles['loading-spinner']} />}
      {local.children}
    </button>
  )
}

export default Button

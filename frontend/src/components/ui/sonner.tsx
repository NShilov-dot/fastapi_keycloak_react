import { type ComponentProps } from 'react'
import { Toaster as Sonner } from 'sonner'

type ToasterProps = ComponentProps<typeof Sonner>

// NOTE: theme is hard-coded to "light" for now. Phase 4 (dark mode) swaps this
// to read next-themes' useTheme() so toasts follow the active colour scheme.
const Toaster = (props: ToasterProps) => {
  return (
    <Sonner
      theme="light"
      className="toaster group"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast:
            'group toast group-[.toaster]:border-border group-[.toaster]:shadow-lg',
          description: 'group-[.toast]:text-muted-foreground',
          actionButton:
            'group-[.toast]:bg-primary group-[.toast]:text-primary-foreground',
          cancelButton:
            'group-[.toast]:bg-muted group-[.toast]:text-muted-foreground',
        },
      }}
      {...props}
    />
  )
}

export { Toaster }

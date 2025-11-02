"""
HQ Command GUI Animation Framework.

Provides reusable animations and transitions.
"""

from typing import Optional

from .qt_compat import (
    QWidget,
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QSequentialAnimationGroup,
    QPoint,
    QSize,
    QGraphicsOpacityEffect,
)
from .styles import theme


class AnimationBuilder:
    """
    Builder for creating common animations.

    Provides factory methods for slide, fade, scale animations.
    """

    @staticmethod
    def fade_in(
        widget: QWidget,
        duration: int = theme.TRANSITION_NORMAL,
        on_finished: Optional[callable] = None,
    ) -> QPropertyAnimation:
        """
        Create fade-in animation.

        Args:
            widget: Widget to animate
            duration: Animation duration in ms
            on_finished: Callback when animation finishes

        Returns:
            Configured animation
        """
        # Create opacity effect if not present
        if not widget.graphicsEffect():
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        effect = widget.graphicsEffect()
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)

        if on_finished:
            animation.finished.connect(on_finished)

        return animation

    @staticmethod
    def fade_out(
        widget: QWidget,
        duration: int = theme.TRANSITION_NORMAL,
        on_finished: Optional[callable] = None,
    ) -> QPropertyAnimation:
        """
        Create fade-out animation.

        Args:
            widget: Widget to animate
            duration: Animation duration in ms
            on_finished: Callback when animation finishes

        Returns:
            Configured animation
        """
        # Create opacity effect if not present
        if not widget.graphicsEffect():
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        effect = widget.graphicsEffect()
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.InCubic)

        if on_finished:
            animation.finished.connect(on_finished)

        return animation

    @staticmethod
    def slide_in_from_right(
        widget: QWidget,
        duration: int = theme.TRANSITION_SLOW,
        distance: Optional[int] = None,
        on_finished: Optional[callable] = None,
    ) -> QPropertyAnimation:
        """
        Create slide-in from right animation.

        Args:
            widget: Widget to animate
            duration: Animation duration in ms
            distance: Distance to slide (None = widget width)
            on_finished: Callback when animation finishes

        Returns:
            Configured animation
        """
        if distance is None:
            distance = widget.width()

        start_pos = widget.pos() + QPoint(distance, 0)
        end_pos = widget.pos()

        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(end_pos)
        animation.setEasingCurve(QEasingCurve.OutCubic)

        if on_finished:
            animation.finished.connect(on_finished)

        return animation

    @staticmethod
    def slide_out_to_right(
        widget: QWidget,
        duration: int = theme.TRANSITION_SLOW,
        distance: Optional[int] = None,
        on_finished: Optional[callable] = None,
    ) -> QPropertyAnimation:
        """
        Create slide-out to right animation.

        Args:
            widget: Widget to animate
            duration: Animation duration in ms
            distance: Distance to slide (None = widget width)
            on_finished: Callback when animation finishes

        Returns:
            Configured animation
        """
        if distance is None:
            distance = widget.width()

        start_pos = widget.pos()
        end_pos = widget.pos() + QPoint(distance, 0)

        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(start_pos)
        animation.setEndValue(end_pos)
        animation.setEasingCurve(QEasingCurve.InCubic)

        if on_finished:
            animation.finished.connect(on_finished)

        return animation

    @staticmethod
    def scale_up(
        widget: QWidget,
        duration: int = theme.TRANSITION_NORMAL,
        scale_factor: float = 1.1,
        on_finished: Optional[callable] = None,
    ) -> QPropertyAnimation:
        """
        Create scale-up animation (grow).

        Args:
            widget: Widget to animate
            duration: Animation duration in ms
            scale_factor: Target scale (1.0 = original size)
            on_finished: Callback when animation finishes

        Returns:
            Configured animation
        """
        original_size = widget.size()
        target_size = QSize(
            int(original_size.width() * scale_factor),
            int(original_size.height() * scale_factor),
        )

        animation = QPropertyAnimation(widget, b"size")
        animation.setDuration(duration)
        animation.setStartValue(original_size)
        animation.setEndValue(target_size)
        animation.setEasingCurve(QEasingCurve.OutCubic)

        if on_finished:
            animation.finished.connect(on_finished)

        return animation

    @staticmethod
    def pulse(
        widget: QWidget,
        duration: int = theme.TRANSITION_FAST,
        scale_factor: float = 1.05,
    ) -> QSequentialAnimationGroup:
        """
        Create pulse animation (scale up then down).

        Args:
            widget: Widget to animate
            duration: Duration for each half of pulse
            scale_factor: Peak scale

        Returns:
            Configured animation group
        """
        group = QSequentialAnimationGroup()

        # Scale up
        up_anim = AnimationBuilder.scale_up(widget, duration, scale_factor)
        group.addAnimation(up_anim)

        # Scale down
        down_anim = AnimationBuilder.scale_up(widget, duration, 1.0)
        group.addAnimation(down_anim)

        return group


class LoadingAnimation:
    """
    Loading animation helper.

    Provides spinning/pulsing indicators.
    """

    @staticmethod
    def create_spinner_effect(widget: QWidget) -> QPropertyAnimation:
        """
        Create spinning rotation effect.

        Args:
            widget: Widget to spin

        Returns:
            Looping rotation animation
        """
        # Note: Basic spinner - can be enhanced with transform animations
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(1000)
        animation.setLoopCount(-1)  # Infinite loop
        animation.setEasingCurve(QEasingCurve.Linear)
        return animation

    @staticmethod
    def create_pulsing_effect(widget: QWidget) -> QPropertyAnimation:
        """
        Create pulsing opacity effect.

        Args:
            widget: Widget to pulse

        Returns:
            Looping opacity animation
        """
        if not widget.graphicsEffect():
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        effect = widget.graphicsEffect()
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(1500)
        animation.setStartValue(0.3)
        animation.setEndValue(1.0)
        animation.setLoopCount(-1)
        animation.setEasingCurve(QEasingCurve.InOutCubic)

        return animation


class TransitionManager:
    """
    Manages state transitions with animations.

    Coordinates multiple animations for complex transitions.
    """

    def __init__(self):
        self.current_animation: Optional[QPropertyAnimation] = None

    def transition_opacity(
        self,
        widget: QWidget,
        target_opacity: float,
        duration: int = theme.TRANSITION_NORMAL,
    ):
        """
        Smoothly transition widget opacity.

        Args:
            widget: Widget to transition
            target_opacity: Target opacity (0.0 to 1.0)
            duration: Transition duration
        """
        if not widget.graphicsEffect():
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        effect = widget.graphicsEffect()
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(duration)
        animation.setEndValue(target_opacity)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        animation.start()

        self.current_animation = animation

    def crossfade(
        self,
        old_widget: QWidget,
        new_widget: QWidget,
        duration: int = theme.TRANSITION_NORMAL,
    ):
        """
        Crossfade between two widgets.

        Args:
            old_widget: Widget to fade out
            new_widget: Widget to fade in
            duration: Crossfade duration
        """
        group = QParallelAnimationGroup()

        # Fade out old
        fade_out = AnimationBuilder.fade_out(old_widget, duration)
        group.addAnimation(fade_out)

        # Fade in new
        fade_in = AnimationBuilder.fade_in(new_widget, duration)
        group.addAnimation(fade_in)

        # Show new widget and start
        new_widget.show()
        group.start()

        # Hide old widget when done
        def cleanup():
            old_widget.hide()

        group.finished.connect(cleanup)

        self.current_animation = group

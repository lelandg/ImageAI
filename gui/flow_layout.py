"""Flow Layout for Qt widgets - wraps items to next line when needed."""

from PySide6.QtWidgets import QLayout, QWidgetItem
from PySide6.QtCore import Qt, QRect, QSize, QPoint


class FlowLayout(QLayout):
    """A layout that arranges widgets in a flow, wrapping to the next line as needed.

    Based on Qt's Flow Layout example.
    """

    def __init__(self, parent=None, margin: int = -1, h_spacing: int = -1, v_spacing: int = -1):
        """Initialize the FlowLayout.

        Args:
            parent: Parent widget
            margin: Layout margin
            h_spacing: Horizontal spacing between items
            v_spacing: Vertical spacing between items
        """
        super().__init__(parent)

        self._item_list = []
        self._h_space = h_spacing
        self._v_space = v_spacing

        if margin != -1:
            self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        """Clean up items."""
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item: QWidgetItem):
        """Add an item to the layout."""
        self._item_list.append(item)

    def horizontalSpacing(self) -> int:
        """Get horizontal spacing between items."""
        if self._h_space >= 0:
            return self._h_space
        else:
            return self._smart_spacing(Qt.Orientation.Horizontal)

    def verticalSpacing(self) -> int:
        """Get vertical spacing between items."""
        if self._v_space >= 0:
            return self._v_space
        else:
            return self._smart_spacing(Qt.Orientation.Vertical)

    def count(self) -> int:
        """Get number of items in layout."""
        return len(self._item_list)

    def itemAt(self, index: int) -> QWidgetItem:
        """Get item at index."""
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int) -> QWidgetItem:
        """Remove and return item at index."""
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        """Return which directions this layout can expand."""
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        """Return True if this layout's height depends on its width."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Calculate height needed for given width."""
        height = self._do_layout(QRect(0, 0, width, 0), test_only=True)
        return height

    def setGeometry(self, rect: QRect):
        """Set the geometry of the layout."""
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        """Return the preferred size of the layout."""
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        """Return the minimum size of the layout."""
        size = QSize()

        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())

        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        """Perform the layout.

        Args:
            rect: Rectangle to lay out items in
            test_only: If True, only calculate height without actually positioning items

        Returns:
            Height needed for layout
        """
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._item_list:
            widget = item.widget()
            space_x = self.horizontalSpacing()
            if space_x == -1:
                space_x = widget.style().layoutSpacing(
                    widget.__class__, widget.__class__, Qt.Orientation.Horizontal
                )

            space_y = self.verticalSpacing()
            if space_y == -1:
                space_y = widget.style().layoutSpacing(
                    widget.__class__, widget.__class__, Qt.Orientation.Vertical
                )

            next_x = x + item.sizeHint().width() + space_x

            if next_x - space_x > effective_rect.right() and line_height > 0:
                # Move to next line
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom

    def _smart_spacing(self, orientation: Qt.Orientation) -> int:
        """Get smart spacing from parent widget style."""
        parent = self.parent()
        if not parent:
            return -1

        if parent.isWidgetType():
            return parent.style().layoutSpacing(
                parent.__class__, parent.__class__, orientation
            )
        else:
            return -1
